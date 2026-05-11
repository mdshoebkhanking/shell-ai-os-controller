import random
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_GAMES")

# Global state for all games (persists during session)
GAME_STATE = {
    "active_game": None,
    "target_number": None,
    "attempts": 0,
    # Trivia state
    "trivia_question": None,
    "trivia_answer": None,
    "trivia_options": None,
    # Word scramble state
    "scramble_word": None,
    "scramble_hint": None,
    # Statistics
    "stats": {
        "total_games": 0,
        "wins": 0,
        "losses": 0,
        "games_played": {
            "guess_number": 0,
            "rock_paper_scissors": 0,
            "coin_flip": 0,
            "dice_roll": 0,
            "trivia": 0,
            "word_scramble": 0,
        }
    }
}

# ──────────────────────────────────────────────
# Trivia Question Bank (30+ questions)
# ──────────────────────────────────────────────
TRIVIA_BANK = {
    "general": [
        {"q": "Duniya ka sabse bada ocean kaun sa hai?", "options": ["A) Atlantic", "B) Pacific", "C) Indian", "D) Arctic"], "answer": "B"},
        {"q": "Rainbow mein kitne colors hote hain?", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C"},
        {"q": "Sabse choti continent kaun si hai?", "options": ["A) Europe", "B) Australia", "C) Antarctica", "D) South America"], "answer": "B"},
        {"q": "Human body mein kitni bones hoti hain?", "options": ["A) 186", "B) 206", "C) 226", "D) 256"], "answer": "B"},
        {"q": "Taj Mahal kahan par hai?", "options": ["A) Delhi", "B) Jaipur", "C) Agra", "D) Lucknow"], "answer": "C"},
        {"q": "Ek saal mein kitne seconds hote hain (approx)?", "options": ["A) 31 million", "B) 31.5 million", "C) 32 million", "D) 30 million"], "answer": "B"},
        {"q": "Coffee beans originally kis country se aaye the?", "options": ["A) Brazil", "B) Colombia", "C) Ethiopia", "D) India"], "answer": "C"},
    ],
    "science": [
        {"q": "Paani ka chemical formula kya hai?", "options": ["A) H2O", "B) CO2", "C) NaCl", "D) O2"], "answer": "A"},
        {"q": "Light ka speed kitna hai (approx)?", "options": ["A) 3 lakh km/s", "B) 3 lakh m/s", "C) 30 lakh km/s", "D) 30 hazar km/s"], "answer": "A"},
        {"q": "DNA ka full form kya hai?", "options": ["A) Di Nucleic Acid", "B) Deoxyribonucleic Acid", "C) Dynamic Nuclear Acid", "D) Dual Nitrogen Acid"], "answer": "B"},
        {"q": "Sabse hard natural substance kaun si hai?", "options": ["A) Gold", "B) Iron", "C) Diamond", "D) Platinum"], "answer": "C"},
        {"q": "Human body ka sabse bada organ kaun sa hai?", "options": ["A) Liver", "B) Brain", "C) Heart", "D) Skin"], "answer": "D"},
        {"q": "Photosynthesis mein plants kya release karte hain?", "options": ["A) CO2", "B) Nitrogen", "C) Oxygen", "D) Hydrogen"], "answer": "C"},
        {"q": "Newton ka pehla law of motion kya kehta hai?", "options": ["A) Force = mass x acceleration", "B) Object at rest stays at rest", "C) Every action has reaction", "D) Energy is conserved"], "answer": "B"},
    ],
    "history": [
        {"q": "India ko independence kab mili?", "options": ["A) 1945", "B) 1947", "C) 1950", "D) 1942"], "answer": "B"},
        {"q": "World War II kab khatam hua?", "options": ["A) 1943", "B) 1944", "C) 1945", "D) 1946"], "answer": "C"},
        {"q": "Pehla computer programmer kaun the?", "options": ["A) Alan Turing", "B) Charles Babbage", "C) Ada Lovelace", "D) John Von Neumann"], "answer": "C"},
        {"q": "Egypt ke pyramids kis liye banaye gaye the?", "options": ["A) Temples", "B) Tombs", "C) Forts", "D) Observatories"], "answer": "B"},
        {"q": "Mughal Empire ka founder kaun tha?", "options": ["A) Akbar", "B) Shah Jahan", "C) Babur", "D) Humayun"], "answer": "C"},
        {"q": "French Revolution kis saal hua tha?", "options": ["A) 1776", "B) 1789", "C) 1799", "D) 1804"], "answer": "B"},
    ],
    "tech": [
        {"q": "Python programming language kisne banayi?", "options": ["A) James Gosling", "B) Guido van Rossum", "C) Dennis Ritchie", "D) Bjarne Stroustrup"], "answer": "B"},
        {"q": "HTML ka full form kya hai?", "options": ["A) Hyper Text Markup Language", "B) High Tech Modern Language", "C) Hyper Transfer Markup Language", "D) Home Tool Markup Language"], "answer": "A"},
        {"q": "Pehla iPhone kab launch hua tha?", "options": ["A) 2005", "B) 2006", "C) 2007", "D) 2008"], "answer": "C"},
        {"q": "Linux kernel kisne banaya?", "options": ["A) Bill Gates", "B) Steve Jobs", "C) Linus Torvalds", "D) Mark Zuckerberg"], "answer": "C"},
        {"q": "AI ka full form kya hai?", "options": ["A) Auto Intelligence", "B) Artificial Intelligence", "C) Advanced Interface", "D) Analog Input"], "answer": "B"},
        {"q": "1 byte mein kitne bits hote hain?", "options": ["A) 4", "B) 8", "C) 16", "D) 32"], "answer": "B"},
    ],
    "sports": [
        {"q": "Cricket World Cup pehli baar kab hua tha?", "options": ["A) 1971", "B) 1975", "C) 1979", "D) 1983"], "answer": "B"},
        {"q": "Football (soccer) team mein kitne players hote hain?", "options": ["A) 9", "B) 10", "C) 11", "D) 12"], "answer": "C"},
        {"q": "Olympic Games kitne saal mein hote hain?", "options": ["A) 2", "B) 3", "C) 4", "D) 5"], "answer": "C"},
        {"q": "Tennis mein Grand Slam kitne tournaments hain?", "options": ["A) 3", "B) 4", "C) 5", "D) 6"], "answer": "B"},
        {"q": "Sachin Tendulkar ne kitne international centuries maare?", "options": ["A) 50", "B) 75", "C) 100", "D) 120"], "answer": "C"},
        {"q": "Basketball mein ek team mein kitne players court pe hote hain?", "options": ["A) 4", "B) 5", "C) 6", "D) 7"], "answer": "B"},
    ],
}

# ──────────────────────────────────────────────
# Word Bank for Word Scramble
# ──────────────────────────────────────────────
WORD_BANK = {
    "easy": [
        ("game", "Ye khelne wali cheez hai"),
        ("code", "Programmers ye likhte hain"),
        ("fish", "Paani mein rehti hai"),
        ("bird", "Aasman mein udti hai"),
        ("rain", "Baarish ko English mein kya kehte hain"),
        ("star", "Raat ko chamakti hai"),
        ("tree", "Ped ko English mein kya kehte hain"),
        ("moon", "Chand ko English mein kya kehte hain"),
        ("fire", "Aag ko English mein kya kehte hain"),
        ("king", "Raja ko English mein kya kehte hain"),
        ("book", "Padhne wali cheez"),
        ("door", "Darwaza ko English mein kya kehte hain"),
    ],
    "medium": [
        ("python", "Ek programming language aur ek saanp"),
        ("rocket", "Space mein jaane wali cheez"),
        ("garden", "Phool wali jagah"),
        ("castle", "Raja ka ghar"),
        ("silver", "Ek precious metal"),
        ("orange", "Ek fruit aur ek color bhi"),
        ("bridge", "Nadi ke upar banta hai"),
        ("guitar", "Ek musical instrument"),
        ("planet", "Earth ek hai"),
        ("coffee", "Subah peene wali cheez"),
        ("monkey", "Bandar ko English mein kya kehte hain"),
        ("jungle", "Jahan sher rehta hai"),
    ],
    "hard": [
        ("elephant", "Sabse bada land animal"),
        ("computer", "Aap isi pe kaam kar rahe ho"),
        ("dinosaur", "Bahut purana extinct animal"),
        ("treasure", "Khajaana ko English mein kya kehte hain"),
        ("butterfly", "Titli ko English mein kya kehte hain"),
        ("crocodile", "Magarmach ko English mein kya kehte hain"),
        ("telephone", "Baat karne wala device"),
        ("chocolate", "Meethi brown cheez"),
        ("adventure", "Ek exciting journey"),
        ("pineapple", "Ek spiky fruit"),
        ("knowledge", "Gyaan ko English mein kya kehte hain"),
        ("fireworks", "Diwali pe chalate hain"),
    ],
}


def _update_stats(game_name: str, won: bool):
    """Helper to update game statistics."""
    GAME_STATE["stats"]["total_games"] += 1
    GAME_STATE["stats"]["games_played"][game_name] += 1
    if won:
        GAME_STATE["stats"]["wins"] += 1
    else:
        GAME_STATE["stats"]["losses"] += 1


def _scramble_word(word: str) -> str:
    """Scramble a word, ensuring it's different from original."""
    letters = list(word)
    for _ in range(20):
        random.shuffle(letters)
        if "".join(letters) != word:
            break
    return "".join(letters)


# ═══════════════════════════════════════════════
# TOOL 1: Rock Paper Scissors
# ═══════════════════════════════════════════════
@function_tool
async def rock_paper_scissors_tool(player_choice: str) -> str:
    """
    Rock Paper Scissors khelo Shell ke saath!
    Args:
        player_choice: 'rock'/'patthar', 'paper'/'kagaz', 'scissors'/'kainchi'
    """
    # Hindi to English mapping
    hindi_map = {
        "patthar": "rock",
        "kagaz": "paper",
        "kainchi": "scissors",
    }

    choice = player_choice.strip().lower()
    choice = hindi_map.get(choice, choice)

    valid_choices = ["rock", "paper", "scissors"]
    if choice not in valid_choices:
        return "❌ boss, sirf 'rock/patthar', 'paper/kagaz', ya 'scissors/kainchi' mein se choose kijiye!"

    computer_choice = random.choice(valid_choices)

    emoji_map = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    result_line = f"\n🤜 Aapka choice: {emoji_map[choice]} {choice.upper()}\n🤖 Mera choice: {emoji_map[computer_choice]} {computer_choice.upper()}\n"

    if choice == computer_choice:
        _update_stats("rock_paper_scissors", False)
        return f"🎮 ROCK PAPER SCISSORS! ✊📄✂️{result_line}\n🤝 DRAW! Dono ne same choose kiya, boss! Ek aur round?"

    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    if win_map[choice] == computer_choice:
        _update_stats("rock_paper_scissors", True)
        return f"🎮 ROCK PAPER SCISSORS! ✊📄✂️{result_line}\n🎉 JEET GAYE, boss! {choice.upper()} beats {computer_choice.upper()}! Kamaal kar diya! 🏆"
    else:
        _update_stats("rock_paper_scissors", False)
        return f"🎮 ROCK PAPER SCISSORS! ✊📄✂️{result_line}\n😅 HAAR GAYE, boss! {computer_choice.upper()} beats {choice.upper()}! Koi nahi, agli baar pakka jeetenge! 💪"


# ═══════════════════════════════════════════════
# TOOL 2: Coin Flip
# ═══════════════════════════════════════════════
@function_tool
async def coin_flip_tool(call: str = "") -> str:
    """
    Virtual coin flip karo! Heads ya Tails?
    Args:
        call: Optional - 'heads' ya 'tails' guess karo pehle se
    """
    result = random.choice(["heads", "tails"])
    emoji_result = "🪙✨" if result == "heads" else "🪙💫"

    flip_animation = (
        "🪙 Coin flip ho raha hai...\n"
        "   ╭─────╮\n"
        "   │ 🪙  │  ↑ FLIP!\n"
        "   ╰─────╯\n"
        "   ... ghoom raha hai ...\n"
        "   ... aur ghoom raha hai ...\n"
        f"   🎯 Result: {emoji_result} **{result.upper()}**!\n"
    )

    if call:
        call = call.strip().lower()
        if call not in ["heads", "tails"]:
            return "❌ boss, sirf 'heads' ya 'tails' bol sakte hain!"

        if call == result:
            _update_stats("coin_flip", True)
            return f"🎮 COIN FLIP!\n{flip_animation}\n🎉 SAHI GUESS, boss! Aapne '{call}' bola aur '{result}' aaya! Lucky ho aap! 🍀"
        else:
            _update_stats("coin_flip", False)
            return f"🎮 COIN FLIP!\n{flip_animation}\n😅 GALAT GUESS, boss! Aapne '{call}' bola lekin '{result}' aaya! Better luck next time! 🤞"
    else:
        _update_stats("coin_flip", True)
        return f"🎮 COIN FLIP!\n{flip_animation}\n💡 boss, agla baar pehle se guess karke dekhiye - 'heads' ya 'tails'!"


# ═══════════════════════════════════════════════
# TOOL 3: Dice Roll
# ═══════════════════════════════════════════════
@function_tool
async def dice_roll_tool(num_dice: int = 1, sides: int = 6) -> str:
    """
    Dice roll karo! Multiple dice aur custom sides supported.
    Args:
        num_dice: Kitne dice roll karne hain (1-10)
        sides: Ek die pe kitne sides hain (2-100)
    """
    if num_dice < 1 or num_dice > 10:
        return "❌ boss, 1 se 10 ke beech dice roll kar sakte hain!"
    if sides < 2 or sides > 100:
        return "❌ boss, die ke sides 2 se 100 ke beech hone chahiye!"

    dice_emoji = ["🎲", "🎯", "💥", "⚡", "🔥", "✨", "💎", "🌟", "🎪", "🎰"]
    results = []
    for i in range(num_dice):
        roll = random.randint(1, sides)
        results.append(roll)

    total = sum(results)
    _update_stats("dice_roll", True)

    # Build result display
    header = f"🎮 DICE ROLL! ({num_dice}d{sides})\n"
    header += "━" * 30 + "\n"

    rolls_display = ""
    for i, r in enumerate(results):
        emoji = dice_emoji[i % len(dice_emoji)]
        rolls_display += f"  {emoji} Die #{i+1}: [ {r} ]\n"

    rolls_display += "━" * 30 + "\n"

    if num_dice > 1:
        rolls_display += f"  📊 Total: {total}\n"
        rolls_display += f"  📈 Average: {total / num_dice:.1f}\n"
        rolls_display += f"  🏆 Highest: {max(results)}\n"
        rolls_display += f"  📉 Lowest: {min(results)}\n"

    # Fun commentary
    if sides == 6:
        if num_dice == 1:
            if total == 6:
                rolls_display += "\n🔥 CHHAKKA! Maximum roll, boss! Zabardast! 🏏"
            elif total == 1:
                rolls_display += "\n😅 Ek aaya! Koi nahi boss, luck bhi rotate karta hai!"
        elif num_dice == 2:
            if total == 12:
                rolls_display += "\n🎉 DOUBLE SIX! Jackpot, boss! Aaj aapka din hai! 🎰"
            elif total == 2:
                rolls_display += "\n🐍 Snake Eyes! Rare roll hai ye, boss!"
            elif results[0] == results[1]:
                rolls_display += f"\n🎯 DOUBLES! Dono dice pe {results[0]} aaya! Nice! 👏"

    return header + rolls_display


# ═══════════════════════════════════════════════
# TOOL 4: Trivia Quiz
# ═══════════════════════════════════════════════
@function_tool
async def trivia_quiz_tool(category: str = "general") -> str:
    """
    Trivia quiz khelo! Different categories mein questions.
    Args:
        category: 'general', 'science', 'history', 'tech', 'sports'
    """
    global GAME_STATE

    category = category.strip().lower()
    if category not in TRIVIA_BANK:
        available = ", ".join(TRIVIA_BANK.keys())
        return f"❌ boss, ye category nahi hai! Available categories: {available}"

    # Pick a random question
    question_data = random.choice(TRIVIA_BANK[category])

    # Store in game state for answer checking
    GAME_STATE["active_game"] = "trivia"
    GAME_STATE["trivia_question"] = question_data["q"]
    GAME_STATE["trivia_answer"] = question_data["answer"]
    GAME_STATE["trivia_options"] = question_data["options"]

    options_display = "\n".join(f"  {opt}" for opt in question_data["options"])

    return (
        f"🧠 TRIVIA QUIZ! (Category: {category.upper()})\n"
        f"{'━' * 35}\n\n"
        f"❓ {question_data['q']}\n\n"
        f"{options_display}\n\n"
        f"{'━' * 35}\n"
        f"💡 boss, apna answer dijiye! (A/B/C/D)\n"
        f"   game_logic_tool use karein action='answer' ke saath"
    )


# ═══════════════════════════════════════════════
# TOOL 5: Word Scramble
# ═══════════════════════════════════════════════
@function_tool
async def word_scramble_tool(difficulty: str = "medium") -> str:
    """
    Word Scramble khelo! Jumbled letters se word guess karo.
    Args:
        difficulty: 'easy' (4-5 letters), 'medium' (6-7 letters), 'hard' (8+ letters)
    """
    global GAME_STATE

    difficulty = difficulty.strip().lower()
    if difficulty not in WORD_BANK:
        return "❌ boss, difficulty 'easy', 'medium', ya 'hard' mein se choose kijiye!"

    # Pick a random word
    word, hint = random.choice(WORD_BANK[difficulty])
    scrambled = _scramble_word(word)

    # Store in game state
    GAME_STATE["active_game"] = "word_scramble"
    GAME_STATE["scramble_word"] = word
    GAME_STATE["scramble_hint"] = hint

    diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

    return (
        f"🔤 WORD SCRAMBLE! {diff_emoji.get(difficulty, '🟡')} ({difficulty.upper()})\n"
        f"{'━' * 35}\n\n"
        f"  Scrambled Word:  ✨ {scrambled.upper()} ✨\n\n"
        f"  📏 Letters: {len(word)}\n"
        f"  💡 Hint: {hint}\n\n"
        f"{'━' * 35}\n"
        f"🤔 boss, sochiye... kaunsa word hai ye?\n"
        f"   game_logic_tool use karein action='unscramble' ke saath"
    )


# ═══════════════════════════════════════════════
# MAIN GAME LOGIC TOOL (Upgraded)
# ═══════════════════════════════════════════════
@function_tool
async def game_logic_tool(action: str, input_val: str = None) -> str:
    """
    Play interactive games with Shell (Guess the Number, Trivia answers, Word Scramble answers, Stats).
    Args:
        action: 'start_guess_number', 'guess', 'answer' (trivia), 'unscramble' (word scramble), 'stats', 'stop'
        input_val: The number, answer, or word boss provides.
    """
    global GAME_STATE

    action = action.lower().strip()

    # ── Start Guess the Number ──
    if action == "start_guess_number":
        GAME_STATE["active_game"] = "guess_number"
        GAME_STATE["target_number"] = random.randint(1, 100)
        GAME_STATE["attempts"] = 0
        return "🎮 Game Started, boss! Maine 1 se 100 ke beech ek number socha hai. Guess kijiye!"

    # ── Guess (Number Game) ──
    elif action == "guess":
        if GAME_STATE["active_game"] != "guess_number":
            return "❌ boss, pehle game start toh kijiye! Bolliye 'Start game'."

        try:
            guess = int(input_val)
            GAME_STATE["attempts"] += 1

            if guess < GAME_STATE["target_number"]:
                return f"📉 Thoda bada number guess karein, boss! (Attempts: {GAME_STATE['attempts']})"
            elif guess > GAME_STATE["target_number"]:
                return f"📈 Thoda chota number guess karein, boss! (Attempts: {GAME_STATE['attempts']})"
            else:
                attempts = GAME_STATE["attempts"]
                GAME_STATE["active_game"] = None
                _update_stats("guess_number", True)
                if attempts <= 3:
                    praise = "GENIUS! Itne kam tries mein? Kya baat hai! 🧠"
                elif attempts <= 7:
                    praise = "Bahut acche, boss! Smart guessing! 🎯"
                else:
                    praise = "Finally mil gaya! Patience ka phal meetha hota hai! 😄"
                return f"🎉 BINGO! Sahi jawab, boss! Aapne sirf {attempts} baar mein dhoondh liya. {praise}"
        except Exception:
            return "❌ boss, please valid number batayiye."

    # ── Answer (Trivia) ──
    elif action == "answer":
        if GAME_STATE["active_game"] != "trivia":
            return "❌ boss, pehle trivia_quiz_tool se ek question lo!"

        if not input_val:
            return "❌ boss, apna answer toh dijiye! (A/B/C/D)"

        user_answer = input_val.strip().upper()
        correct = GAME_STATE["trivia_answer"]

        # Find the correct option text
        correct_text = ""
        for opt in GAME_STATE["trivia_options"]:
            if opt.startswith(correct + ")"):
                correct_text = opt
                break

        GAME_STATE["active_game"] = None

        if user_answer == correct:
            _update_stats("trivia", True)
            return (
                f"🎉 SAHI JAWAB, boss! ✅\n\n"
                f"  Correct Answer: {correct_text}\n\n"
                f"🧠 Aapka knowledge toh kamaal hai! Ek aur question chahiye?"
            )
        else:
            _update_stats("trivia", False)
            return (
                f"😅 GALAT JAWAB, boss! ❌\n\n"
                f"  Aapka Answer: {user_answer}\n"
                f"  Correct Answer: {correct_text}\n\n"
                f"📚 Koi nahi, har galti se kuch seekhte hain! Try another question?"
            )

    # ── Unscramble (Word Scramble) ──
    elif action == "unscramble":
        if GAME_STATE["active_game"] != "word_scramble":
            return "❌ boss, pehle word_scramble_tool se ek word lo!"

        if not input_val:
            return "❌ boss, apna guess toh dijiye!"

        user_guess = input_val.strip().lower()
        correct_word = GAME_STATE["scramble_word"]

        GAME_STATE["active_game"] = None

        if user_guess == correct_word:
            _update_stats("word_scramble", True)
            return (
                f"🎉 BILKUL SAHI, boss! ✅\n\n"
                f"  Word: ✨ {correct_word.upper()} ✨\n\n"
                f"🔤 Aapki vocabulary toh zabardast hai! Ek aur word scramble?"
            )
        else:
            _update_stats("word_scramble", False)
            return (
                f"😅 GALAT GUESS, boss! ❌\n\n"
                f"  Aapka Guess: {user_guess.upper()}\n"
                f"  Correct Word: ✨ {correct_word.upper()} ✨\n"
                f"  Hint tha: {GAME_STATE['scramble_hint']}\n\n"
                f"📖 Koi nahi, next time pakka! Try another scramble?"
            )

    # ── Game Statistics ──
    elif action == "stats":
        stats = GAME_STATE["stats"]
        total = stats["total_games"]
        wins = stats["wins"]
        losses = stats["losses"]
        win_rate = (wins / total * 100) if total > 0 else 0

        games = stats["games_played"]

        stats_display = (
            f"📊 GAME STATISTICS\n"
            f"{'═' * 35}\n\n"
            f"  🎮 Total Games:  {total}\n"
            f"  🏆 Wins:         {wins}\n"
            f"  😅 Losses:       {losses}\n"
            f"  📈 Win Rate:     {win_rate:.1f}%\n\n"
            f"{'─' * 35}\n"
            f"  Games Breakdown:\n"
            f"  🔢 Guess Number:       {games['guess_number']}\n"
            f"  ✊ Rock Paper Scissors: {games['rock_paper_scissors']}\n"
            f"  🪙 Coin Flip:          {games['coin_flip']}\n"
            f"  🎲 Dice Roll:          {games['dice_roll']}\n"
            f"  🧠 Trivia Quiz:        {games['trivia']}\n"
            f"  🔤 Word Scramble:      {games['word_scramble']}\n"
            f"{'═' * 35}\n"
        )

        if total == 0:
            stats_display += "\n💡 Abhi tak koi game nahi khela! Chalo kuch khelein, boss!"
        elif win_rate >= 70:
            stats_display += "\n🔥 boss, aap toh champion ho! Kya performance hai!"
        elif win_rate >= 40:
            stats_display += "\n💪 Acchi performance, boss! Keep it up!"
        else:
            stats_display += "\n📚 Practice makes perfect, boss! Aur khelein!"

        return stats_display

    # ── Stop Game ──
    elif action == "stop":
        GAME_STATE["active_game"] = None
        GAME_STATE["trivia_question"] = None
        GAME_STATE["trivia_answer"] = None
        GAME_STATE["scramble_word"] = None
        return "🛑 Theek hai boss, game stop kar diya. Kuch aur kaam karein?"

    # ── Unknown Action ──
    return (
        "❓ boss, kya karna chahte hain? Available actions:\n"
        "  🔢 'start_guess_number' - Number guessing game\n"
        "  🎯 'guess' - Number guess karo\n"
        "  📝 'answer' - Trivia ka jawab do (A/B/C/D)\n"
        "  🔤 'unscramble' - Word scramble ka jawab do\n"
        "  📊 'stats' - Game statistics dekho\n"
        "  🛑 'stop' - Current game band karo"
    )
