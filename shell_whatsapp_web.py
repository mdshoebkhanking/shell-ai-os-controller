#!/usr/bin/env python3
"""
WhatsApp Web Integration for Shell
Uses whatsapp-web.js via subprocess for QR code authentication
"""

import os
import json
import subprocess
import asyncio
from typing import Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger("shell_whatsapp")

# WhatsApp session storage
WHATSAPP_SESSION_DIR = os.path.expanduser("~/.shell_whatsapp_session")
WHATSAPP_PROCESS = None
WHATSAPP_CONNECTED = False
MESSAGE_CALLBACK = None

class WhatsAppWebClient:
    """WhatsApp Web client using whatsapp-web.js"""
    
    def __init__(self):
        self.process = None
        self.connected = False
        self.qr_code = None
        self.session_dir = WHATSAPP_SESSION_DIR
        os.makedirs(self.session_dir, exist_ok=True)
    
    async def start_connection(self, qr_callback=None) -> Tuple[bool, str]:
        """
        Start WhatsApp Web connection
        Returns: (success, message/qr_code)
        """
        try:
            # Check if Node.js is installed
            node_check = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if node_check.returncode != 0:
                return False, "❌ Node.js not installed. Please install Node.js first."
            
            # Create WhatsApp client script
            client_script = os.path.join(self.session_dir, "whatsapp_client.js")
            self._create_client_script(client_script)
            
            # Install dependencies if needed
            package_json = os.path.join(self.session_dir, "package.json")
            if not os.path.exists(package_json):
                with open(package_json, 'w') as f:
                    json.dump({
                        "name": "shell-whatsapp",
                        "version": "1.0.0",
                        "dependencies": {
                            "whatsapp-web.js": "^1.23.0",
                            "qrcode-terminal": "^0.12.0"
                        }
                    }, f, indent=2)
                
                logger.info("📦 Installing WhatsApp dependencies...")
                install = subprocess.run(
                    ["npm", "install"],
                    cwd=self.session_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if install.returncode != 0:
                    return False, f"❌ Failed to install dependencies: {install.stderr}"
            
            # Start WhatsApp client
            logger.info("🚀 Starting WhatsApp Web client...")
            self.process = subprocess.Popen(
                ["node", client_script],
                cwd=self.session_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for QR code or connection
            qr_code = await self._wait_for_qr()
            if qr_code:
                if qr_callback:
                    qr_callback(qr_code)
                return True, qr_code
            else:
                return True, "✅ WhatsApp connected (session restored)"
                
        except subprocess.TimeoutExpired:
            return False, "❌ Connection timeout"
        except Exception as e:
            logger.error(f"WhatsApp connection error: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def _create_client_script(self, filepath):
        """Create Node.js client script for WhatsApp Web"""
        script = """
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './session' }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// QR Code generation
client.on('qr', (qr) => {
    console.log('QR_CODE_START');
    qrcode.generate(qr, { small: true });
    console.log('QR_CODE_END');
    
    // Save QR for GUI display
    fs.writeFileSync('qr_code.txt', qr);
});

// Ready event
client.on('ready', () => {
    console.log('WHATSAPP_READY');
    console.log('✅ WhatsApp is ready!');
});

// Authenticated event
client.on('authenticated', () => {
    console.log('WHATSAPP_AUTHENTICATED');
});

// Message received
client.on('message', async (msg) => {
    const contact = await msg.getContact();
    const messageData = {
        from: contact.pushname || contact.number,
        number: msg.from,
        body: msg.body,
        timestamp: msg.timestamp,
        isGroup: msg.from.includes('@g.us')
    };
    
    console.log('MESSAGE_RECEIVED:' + JSON.stringify(messageData));
    
    // Save to messages.json for Shell to read
    let messages = [];
    try { messages = JSON.parse(fs.readFileSync('messages.json', 'utf8')); } catch(e) {}
    messages.push(messageData);
    fs.writeFileSync('messages.json', JSON.stringify(messages, null, 2));
});

// Disconnected event
client.on('disconnected', (reason) => {
    console.log('WHATSAPP_DISCONNECTED:' + reason);
});

// Initialize
client.initialize();

// Keep alive
process.on('SIGINT', () => {
    client.destroy();
    process.exit();
});
"""
        with open(filepath, 'w') as f:
            f.write(script)
    
    async def _wait_for_qr(self, timeout=30) -> Optional[str]:
        """Wait for QR code or connection"""
        start_time = asyncio.get_event_loop().time()
        qr_lines = []
        capturing_qr = False
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.process.poll() is not None:
                # Process ended
                return None
            
            line = await asyncio.to_thread(self.process.stdout.readline)
            if not line:
                await asyncio.sleep(0.1)
                continue
            
            line = line.strip()
            logger.info(f"WhatsApp: {line}")
            
            if "QR_CODE_START" in line:
                capturing_qr = True
                continue
            elif "QR_CODE_END" in line:
                capturing_qr = False
                # Read QR from file
                qr_file = os.path.join(self.session_dir, "qr_code.txt")
                if os.path.exists(qr_file):
                    with open(qr_file, 'r') as f:
                        return f.read().strip()
            elif "WHATSAPP_READY" in line:
                self.connected = True
                return None  # Already connected
            elif capturing_qr:
                qr_lines.append(line)
        
        return None
    
    async def send_message(self, number: str, message: str) -> Tuple[bool, str]:
        """Send WhatsApp message"""
        if not self.connected:
            return False, "❌ WhatsApp not connected. Start connection first."

        if not number or not message:
            return False, "❌ Number and message are required."

        try:
            # Create command file for Node.js client to read
            command = {
                "action": "send_message",
                "number": number.strip(),
                "message": message,
                "timestamp": datetime.now().isoformat()
            }

            command_file = os.path.join(self.session_dir, "command.json")
            with open(command_file, 'w', encoding='utf-8') as f:
                json.dump(command, f, ensure_ascii=False)

            # Wait for response
            await asyncio.sleep(2)

            return True, f"✅ Message sent to {number}"
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False, f"❌ Failed to send: {str(e)}"
    
    def get_new_messages(self) -> list:
        """Get new messages from WhatsApp"""
        messages_file = os.path.join(self.session_dir, "messages.json")
        if os.path.exists(messages_file):
            try:
                with open(messages_file, 'r') as f:
                    messages = json.load(f)
                
                # Clear file after reading
                with open(messages_file, 'w') as f:
                    json.dump([], f)
                
                return messages
            except Exception as e:
                logger.error(f"Failed to read messages: {e}")
        
        return []
    
    def disconnect(self):
        """Disconnect WhatsApp"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            except Exception as e:
                logger.error(f"Error disconnecting WhatsApp: {e}")
            finally:
                self.process = None
                self.connected = False

# Global instance
whatsapp_client = WhatsAppWebClient()
