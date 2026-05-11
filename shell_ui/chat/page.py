"""Chat UI compatibility module.

The classes are still implemented in shell_cinematic_full during the first
safe extraction phase. New imports should target this module so future moves do
not touch call sites.
"""

from shell_ui.shell_cinematic_full import ChatBubble, ChatPage, TypingIndicator

