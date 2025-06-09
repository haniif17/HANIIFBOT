import discord
import os
from dotenv import load_dotenv
import random
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta

# --- Muat Variabel Lingkungan dari File .env ---
load_dotenv()

# Ambil token bot dari environment variable
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("Error: DISCORD_TOKEN tidak ditemukan. Pastikan sudah diatur di environment variable atau file .env.")
    exit()

# Ambil detail koneksi MySQL dari environment variable
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

# Pastikan semua variabel lingkungan MySQL yang diperlukan sudah diatur
if not all([MYSQL_HOST, MYSQL_USER, MYSQL_DATABASE]):
    print("Error: Pastikan semua variabel lingkungan MySQL (MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE) diatur.")
    exit()

# --- DAFTAR ID ROLE YANG DIIZINKAN UNTUK MENGGUNAKAN !setadmin, !addcash, !removecash ---
ALLOWED_SETADMIN_ROLES = [
    1381168735112659015 # Ini adalah Role ID yang Anda berikan
]
if not ALLOWED_SETADMIN_ROLES:
    print("PERINGATAN: ALLOWED_SETADMIN_ROLES kosong. Tidak ada role yang bisa menggunakan !setadmin, !addcash, !removecash.")

# --- Definisi Intents Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True


# Membuat instance bot
client = discord.Client(intents=intents)

# --- Kelas dan Fungsi untuk Logika Permainan Blackjack ---
class BlackjackGame:
    def __init__(self, player_id: int, bet_amount: int):
        self.player_id = player_id
        self.bet_amount = bet_amount
        self.deck = self._create_shuffled_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_active = False

    def _create_shuffled_deck(self):
        suits = ['♠️', '♥️', '♦️', '♣️']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck

    def _get_card_value(self, card):
        rank = card[0]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11
        else:
            return int(rank)

    def _calculate_hand_value(self, hand):
        value = 0
        num_aces = 0
        for card in hand:
            card_value = self._get_card_value(card)
            if card_value == 11:
                num_aces += 1
            value += card_value

        while value > 21 and num_aces > 0:
            value -= 10
            num_aces -= 1
        return value

    def _deal_card(self, hand):
        card = self.deck.pop()
        hand.append(card)
        return card

    def start_game(self):
        self.game_active = True
        self.player_hand = []
        self.dealer_hand = []
        self._deal_card(self.player_hand)
        self._deal_card(self.dealer_hand)
        self._deal_card(self.player_hand)
        self._deal_card(self.dealer_hand)

        player_score = self._calculate_hand_value(self.player_hand)
        
        if player_score == 21:
            return "blackjack_player"
        return "game_started"

    def hit(self):
        self._deal_card(self.player_hand)
        player_score = self._calculate_hand_value(self.player_hand)
        if player_score > 21:
            return "bust"
        return "continue"

    def stand(self):
        while self._calculate_hand_value(self.dealer_hand) < 17:
            self._deal_card(self.dealer_hand)
        
        player_score = self._calculate_hand_value(self.player_hand)
        dealer_score = self._calculate_hand_value(self.dealer_hand)

        if dealer_score > 21:
            return "dealer_bust"
        elif player_score > dealer_score:
            return "player_win"
        elif dealer_score > player_score: # PERBAIKAN BUG: sebelumnya (dealer_score > dealer_score)
            return "dealer_win"
        else:
            return "tie"
            
    def get_player_hand_str(self):
        return ' '.join([f"{c[0]}{c[1]}" for c in self.player_hand])

    def get_dealer_hand_str(self, hidden=False):
        if hidden:
            return f"{self.dealer_hand[0][0]}{self.dealer_hand[0][1]} [HIDDEN CARD]"
        else:
            return ' '.join([f"{c[0]}{c[1]}" for c in self.dealer_hand])

active_blackjack_games = {} 
blackjack_message_to_player = {}

# --- Kelas dan Dictionary untuk Logika Permainan Flip Coin ---
class FlipCoinGame:
    def __init__(self, player_id: int, bet_amount: int):
        self.player_id = player_id
        self.bet_amount = bet_amount
        self.game_active = True # Game aktif sampai pemain memilih
        self.player_choice = None # Pilihan pemain akan disimpan di sini

active_flipcoin_games = {}
FLIPCOIN_HEAD_EMOJI = '🪙' # Koin
FLIPCOIN_TAIL_EMOJI = '🔵' # Lingkaran Biru

# --- Roulette Game Constants ---
ROULETTE_NUMBERS = {
    0: 'hijau',
    1: 'merah', 2: 'hitam', 3: 'merah', 4: 'hitam', 5: 'merah', 6: 'hitam',
    7: 'merah', 8: 'hitam', 9: 'merah', 10: 'hitam', 11: 'hitam', 12: 'merah',
    13: 'hitam', 14: 'merah', 15: 'hitam', 16: 'merah', 17: 'hitam', 18: 'merah',
    19: 'merah', 20: 'hitam', 21: 'merah', 22: 'hitam', 23: 'merah', 24: 'hitam',
    25: 'merah', 26: 'hitam', 27: 'merah', 28: 'hitam', 29: 'hitam', 30: 'merah',
    31: 'hitam', 32: 'merah', 33: 'hitam', 34: 'merah', 35: 'hitam', 36: 'merah'
}

# Mapping untuk taruhan Dozens dan Columns
ROULETTE_DOZENS = {
    '1st12': list(range(1, 13)),   # 1-12
    '2nd12': list(range(13, 25)),  # 13-24
    '3rd12': list(range(25, 37))   # 25-36
}
ROULETTE_COLUMNS = { # (1, 4, 7...34), (2, 5, 8...35), (3, 6, 9...36)
    'col1': [n for n in range(1, 37) if n % 3 == 1],
    'col2': [n for n in range(1, 37) if n % 3 == 2],
    'col3': [n for n in range(1, 37) if n % 3 == 0]
}

# Pembayaran (Payouts)
ROULETTE_PAYOUTS = {
    'number': 35,  # 1 to 1 for a single number (35:1)
    'color': 1,    # 1 to 1 (1:1)
    'parity': 1,   # 1 to 1 (1:1) (odd/even)
    'half': 1,     # 1 to 1 (1:1) (high/low)
    'dozen': 2,    # 2 to 1 (2:1)
    'column': 2    # 2 to 1 (2:1)
}

# State management untuk roulette
current_roulette_rounds = {} # {channel_id: {"status": "betting", "round_id": str, "message_id": int, "bets": {user_id: [taruhan]}}}
ROULETTE_RED_EMOJI = '🔴'
ROULETTE_BLACK_EMOJI = '⚫' # Menggunakan emoji hitam untuk warna hitam
ROULETTE_BET_MESSAGE_TO_USER = {} # {message_id: channel_id} agar on_reaction_add bisa cari round_id

# --- Fungsi-fungsi untuk Interaksi Database MySQL ---

def get_db_connection():
    """Mencoba membuat koneksi ke database MySQL."""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"ERROR KONEKSI DATABASE: {e}")
        return None

async def get_user_data(user_id: int) -> dict:
    """Mengambil data pengguna (cash dan last_daily_claim) dari database. Jika tidak ada, membuat entri baru."""
    conn = get_db_connection()
    if conn is None: return {"cash": 0, "last_daily_claim": None}
    
    cursor = conn.cursor() 
    try:
        cursor.execute("SELECT cash, last_daily_claim FROM users_cash WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"cash": result[0], "last_daily_claim": result[1]}
        else:
            cursor.execute("INSERT INTO users_cash (user_id, cash, last_daily_claim) VALUES (%s, %s, %s)", (user_id, 0, None))
            conn.commit()
            return {"cash": 0, "last_daily_claim": None}
    except Error as e:
        print(f"ERROR MENGAMBIL DATA PENGGUNA ({user_id}): {e}")
        return {"cash": 0, "last_daily_claim": None}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def update_user_cash(user_id: int, new_amount: int) -> bool:
    """Memperbarui jumlah uang pengguna di database."""
    conn = get_db_connection()
    if conn is None: return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users_cash (user_id, cash) VALUES (%s, %s) "
                       "ON DUPLICATE KEY UPDATE cash = %s", 
                       (user_id, new_amount, new_amount))
        conn.commit()
        return True
    except Error as e:
        print(f"ERROR UPDATE UANG PENGGUNA ({user_id}): {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def update_last_daily_claim(user_id: int, timestamp: datetime) -> bool:
    """Memperbarui timestamp klaim daily terakhir pengguna di database."""
    conn = get_db_connection()
    if conn is None: return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users_cash (user_id, last_daily_claim) VALUES (%s, %s) "
                       "ON DUPLICATE KEY UPDATE last_daily_claim = %s",
                       (user_id, timestamp, timestamp))
        conn.commit()
        return True
    except Error as e:
        print(f"ERROR UPDATE DAILY CLAIM ({user_id}): {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- Fungsi untuk Manajemen Admin Bot ---
async def is_admin_cash_adder(user_id: int) -> bool:
    """Memeriksa apakah user_id adalah admin penambah cash dari database."""
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM bot_admins WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result is not None
    except Error as e:
        print(f"ERROR CEK ADMIN ({user_id}): {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def add_admin_cash_adder(user_id: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT IGNORE INTO bot_admins (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"ERROR TAMBAH ADMIN ({user_id}): {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def remove_admin_cash_adder(user_id: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bot_admins WHERE user_id = %s", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"ERROR HAPUS ADMIN ({user_id}): {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- Fungsi untuk Roulette ---
async def add_roulette_bet(round_id: str, user_id: int, bet_type: str, bet_choice: str, amount: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO roulette_bets (round_id, user_id, bet_type, bet_choice, amount) VALUES (%s, %s, %s, %s, %s)",
            (round_id, user_id, bet_type, bet_choice, amount)
        )
        conn.commit()
        return True
    except Error as e:
        print(f"ERROR ADD ROULETTE BET: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def get_roulette_bets_for_round(round_id: str) -> list[dict]:
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, bet_type, bet_choice, amount FROM roulette_bets WHERE round_id = %s", (round_id,))
        return cursor.fetchall()
    except Error as e:
        print(f"ERROR GET ROULETTE BETS: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def clear_roulette_bets(round_id: str) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM roulette_bets WHERE round_id = %s", (round_id,))
        conn.commit()
        return True
    except Error as e:
        print(f"ERROR CLEAR ROULETTE BETS: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- Event Bot Siap ---
@client.event
async def on_ready():
    print(f'Bot {client.user} berhasil login!')
    print(f'ID Bot: {client.user.id}')
    # Mengupdate status bot untuk hanya menampilkan game yang ada
    await client.change_presence(activity=discord.Game(name="main !blackjack, !flipcoin, !roulette"))
    print("Bot siap melayani perintah!")

# --- Event Bot Menerima Reaksi (Diperbarui untuk Flip Coin) ---
@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    # --- Logika untuk Blackjack ---
    if reaction.message.id in blackjack_message_to_player:
        player_id_in_game = blackjack_message_to_player[reaction.message.id]
        
        if user.id != player_id_in_game:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                print("Bot tidak memiliki izin untuk menghapus reaksi.")
            return
        
        game = active_blackjack_games.get(user.id)
        if not game or not game.game_active:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                pass
            del blackjack_message_to_player[reaction.message.id]
            return

        try:
            await reaction.message.remove_reaction(reaction.emoji, user)
        except discord.Forbidden:
            print("Bot tidak memiliki izin untuk menghapus reaksi.")

        if str(reaction.emoji) == '✅': # HIT
            result = game.hit()
            player_hand_str = game.get_player_hand_str()
            player_score = game._calculate_hand_value(game.player_hand)

            if result == "bust":
                dealer_hand_str_revealed = game.get_dealer_hand_str(hidden=False)
                dealer_score = game._calculate_hand_value(game.dealer_hand)
                await reaction.message.channel.send(
                    f"**{user.display_name} HIT!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"💥 **Anda Bust! Kartu Anda melebihi 21. Anda kalah {game.bet_amount} koin!** 💸"
                )
                del active_blackjack_games[user.id]
                del blackjack_message_to_player[reaction.message.id]
            else:
                dealer_hand_str_current = game.get_dealer_hand_str(hidden=False)
                dealer_score_current = game._calculate_hand_value(game.dealer_hand)
                new_message = await reaction.message.channel.send(
                    f"**{user.display_name} HIT!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_current} (Total: {dealer_score_current})\n"
                    "Klik ✅ untuk HIT atau 🟥 untuk STAND."
                )
                blackjack_message_to_player[new_message.id] = user.id
                if reaction.message.id in blackjack_message_to_player:
                    del blackjack_message_to_player[reaction.message.id]
                await new_message.add_reaction('✅')
                await new_message.add_reaction('🟥')

        elif str(reaction.emoji) == '🟥': # STAND
            result = game.stand()
            player_hand_str = game.get_player_hand_str()
            player_score = game._calculate_hand_value(game.player_hand)
            dealer_hand_str_revealed = game.get_dealer_hand_str(hidden=False)
            dealer_score = game._calculate_hand_value(game.dealer_hand)
            
            bet_amount = game.bet_amount

            if result == "dealer_bust":
                user_data = await get_user_data(user.id)
                final_cash = user_data["cash"] + (bet_amount * 2)
                await update_user_cash(user.id, final_cash)
                response_message = (
                    f"**{user.display_name} memutuskan untuk STAND!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"🎉 **DEALER BUST! Anda menang {bet_amount * 2} koin!** 🎉"
                )
            elif result == "player_win":
                user_data = await get_user_data(user.id)
                final_cash = user_data["cash"] + (bet_amount * 2)
                await update_user_cash(user.id, final_cash)
                response_message = (
                    f"**{user.display_name} memutuskan untuk STAND!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"💰 **Anda menang {bet_amount * 2} koin! Selamat!** 🥳"
                )
            elif result == "dealer_win":
                response_message = (
                    f"**{user.display_name} memutuskan untuk STAND!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"💔 **DEALER MENANG! Anda kalah {bet_amount} koin.** 😥"
                )
            elif result == "tie":
                user_data = await get_user_data(user.id)
                final_cash = user_data["cash"] + bet_amount
                await update_user_cash(user.id, final_cash)
                response_message = (
                    f"**{user.display_name} memutuskan untuk STAND!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"🤝 **Ini seri! Taruhan {bet_amount} koin Anda dikembalikan.**"
                )
            
            await reaction.message.channel.send(response_message)
            del active_blackjack_games[user.id]
            del blackjack_message_to_player[reaction.message.id]

    # --- Logika untuk Flip Coin (BARU) ---
    elif reaction.message.id in active_flipcoin_games:
        game = active_flipcoin_games.get(reaction.message.id)

        if user.id != game.player_id:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                print("Bot tidak memiliki izin untuk menghapus reaksi.")
            return

        if not game.game_active:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                pass
            del active_flipcoin_games[reaction.message.id] # Hapus dari pelacakan jika sudah selesai
            return

        try:
            await reaction.message.remove_reaction(reaction.emoji, user)
        except discord.Forbidden:
            print("Bot tidak memiliki izin untuk menghapus reaksi.")
        
        user_choice_str = ""
        if str(reaction.emoji) == FLIPCOIN_HEAD_EMOJI:
            user_choice_str = "kepala"
        elif str(reaction.emoji) == FLIPCOIN_TAIL_EMOJI:
            user_choice_str = "ekor"
        else: # Reaksi bukan emoji pilihan
            return

        game.player_choice = user_choice_str # Simpan pilihan pemain
        game.game_active = False # Tandai game tidak lagi aktif menunggu pilihan

        # Lakukan lemparan koin
        coin_sides = ['kepala', 'ekor']
        coin_result = random.choice(coin_sides)
        
        result_message = ""
        user_data = await get_user_data(user.id)
        current_cash = user_data["cash"]
        
        if user_choice_str == coin_result:
            winning_amount = game.bet_amount * 2
            final_cash = current_cash + winning_amount
            await update_user_cash(user.id, final_cash)
            result_message = (
                f"🎉 **LEMPAR KOIN! Anda Menang!** 🎉\n"
                f"Anda memilih **{user_choice_str.upper()}**. Koin mendarat di **{coin_result.upper()}**!\n"
                f"Selamat, **{user.display_name}**! Anda memenangkan **{winning_amount} koin**!\n"
                f"Uang Anda sekarang: **{final_cash} koin**."
            )
            print(f"{user.name} menang {winning_amount} di flipcoin.")
        else:
            final_cash = current_cash
            result_message = (
                f"💔 **LEMPAR KOIN! Anda Kalah.** 💔\n"
                f"Anda memilih **{user_choice_str.upper()}**. Koin mendarat di **{coin_result.upper()}**!\n"
                f"Maaf, **{user.display_name}**. Anda kalah **{game.bet_amount} koin**.\n"
                f"Uang Anda sekarang: **{final_cash} koin**."
            )
            print(f"{user.name} kalah {game.bet_amount} di flipcoin.")
        
        await reaction.message.channel.send(result_message)
        del active_flipcoin_games[reaction.message.id]
        await reaction.message.clear_reactions()

    # --- Logika untuk Roulette (TARUHAN VIA REAKSI) ---
    elif reaction.message.id in ROULETTE_BET_MESSAGE_TO_USER: # Cek apakah ini pesan taruhan roulette
        channel_id_for_roulette = ROULETTE_BET_MESSAGE_TO_USER[reaction.message.id]

        if channel_id_for_roulette in current_roulette_rounds and \
           current_roulette_rounds[channel_id_for_roulette]["status"] == "betting":
            
            roulette_round = current_roulette_rounds[channel_id_for_roulette]
            round_id = roulette_round["round_id"]

            if user.bot:
                return
            
            # Periksa apakah pengguna sudah bertaruh warna di putaran ini
            user_bets = roulette_round["bets"].get(user.id, [])
            if any(b['bet_type'] == 'color' and b.get('via_emoji', False) for b in user_bets):
                 await reaction.message.channel.send(f"**{user.display_name}**, Anda sudah memasang taruhan warna via emoji di putaran ini. Gunakan `!bet` untuk taruhan lain.", ephemeral=True) # Perbaikan: Hapus ephemeral
                 try: await reaction.message.remove_reaction(reaction.emoji, user)
                 except discord.Forbidden: pass
                 return

            bet_amount = 10 # Default taruhan untuk reaksi warna
            bet_type = 'color'
            bet_choice = None

            if str(reaction.emoji) == ROULETTE_RED_EMOJI:
                bet_choice = 'merah'
            elif str(reaction.emoji) == ROULETTE_BLACK_EMOJI:
                bet_choice = 'hitam'
            
            if not bet_choice: # Emoji bukan untuk taruhan warna roulette
                try: await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.Forbidden: pass
                return
            
            user_data = await get_user_data(user.id)
            current_cash = user_data["cash"]
            if current_cash < bet_amount:
                await reaction.message.channel.send(f"**{user.display_name}**, uang Anda tidak cukup ({current_cash} koin) untuk taruhan {bet_amount} koin.") # Perbaikan: Hapus ephemeral
                try: await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.Forbidden: pass
                return
            
            new_cash = current_cash - bet_amount
            await update_user_cash(user.id, new_cash)
            
            # Tambahkan taruhan ke DB
            success_bet = await add_roulette_bet(round_id, user.id, bet_type, bet_choice, bet_amount)
            
            if success_bet:
                if user.id not in roulette_round["bets"]:
                    roulette_round["bets"][user.id] = [] # Inisialisasi daftar taruhan untuk user ini
                roulette_round["bets"][user.id].append({"amount": bet_amount, "bet_type": bet_type, "bet_choice": bet_choice, "via_emoji": True})
                await reaction.message.channel.send(
                    f"**{user.display_name}** menempatkan taruhan **{bet_amount} koin** pada **{bet_choice.upper()}** (via emoji). Uang Anda sekarang: **{new_cash} koin**."
                )
                print(f"{user.name} menaruh {bet_amount} koin di roulette via emoji.")
            else:
                await reaction.message.channel.send(f"Gagal menempatkan taruhan Roulette. Terjadi kesalahan database.") # Perbaikan: Hapus ephemeral
                await update_user_cash(user.id, current_cash) # Kembalikan uang jika gagal
                print(f"WARNING: Taruhan Roulette via emoji {user.id} gagal DB, uang dikembalikan.")
            
            try: await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden: pass
        else: # Bukan putaran roulette aktif yang menunggu reaksi
            try: await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.Forbidden: pass


# --- Event Bot Menerima Pesan ---
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    msg_content = message.content.lower()
    user_id = message.author.id
    channel_id = message.channel.id # Untuk Roulette

    def has_required_role(member: discord.Member, allowed_roles: list[int]) -> bool:
        if not member.guild:
            return False
        if not allowed_roles:
            return False
        for role in member.roles:
            if role.id in allowed_roles:
                return True
        return False

    if msg_content.startswith('!setadmin '):
        if not message.guild:
            await message.channel.send("Perintah ini hanya bisa digunakan di dalam server Discord.")
            return

        if not has_required_role(message.author, ALLOWED_SETADMIN_ROLES):
            await message.channel.send("Maaf, Anda tidak memiliki role yang diperlukan untuk menggunakan perintah ini.")
            return
        
        parts = message.content.split()
        if len(parts) >= 3:
            action = parts[1].lower()
            target_id_str = parts[2]
            
            try:
                target_user = None
                if message.mentions:
                    target_user = message.mentions[0]
                    target_user_id = target_user.id
                else:
                    target_user_id = int(target_id_str)
                    try:
                        target_user = await client.fetch_user(target_user_id)
                    except discord.NotFound:
                        await message.channel.send("ID pengguna tidak valid atau tidak ditemukan.")
                        return

                if action == 'add':
                    success = await add_admin_cash_adder(target_user_id)
                    if success:
                        await message.channel.send(f"{target_user.display_name} ({target_user_id}) sekarang adalah admin penambah cash.")
                        print(f"Admin {message.author.name} menambahkan {target_user.name} sebagai admin cash.")
                    else:
                        await message.channel.send(f"{target_user.display_name} ({target_user_id}) sudah menjadi admin penambah cash.")
                elif action == 'remove':
                    success = await remove_admin_cash_adder(target_user_id)
                    if success:
                        await message.channel.send(f"{target_user.display_name} ({target_user_id}) telah dihapus dari admin penambah cash.")
                        print(f"Admin {message.author.name} menghapus {target_user.name} dari admin cash.")
                    else:
                        await message.channel.send(f"{target_user.display_name} ({target_user_id}) bukan admin penambah cash.")
                else:
                    await message.channel.send("Format yang benar: `!setadmin [add/remove] <Discord ID/@user>`")
            except ValueError:
                await message.channel.send("Format ID pengguna tidak valid. Gunakan ID angka atau mention.")
            except Exception as e:
                await message.channel.send(f"Terjadi kesalahan: {e}")
        else:
            await message.channel.send("Format yang benar: `!setadmin [add/remove] <Discord ID/@user>`")

    elif msg_content == '!balance':
        user_data = await get_user_data(user_id)
        user_current_cash = user_data["cash"]
        await message.channel.send(f"{message.author.mention}, uang kamu saat ini: **{user_current_cash} koin**.")
        print(f"Merespons '!balance' dari {message.author.name}. Uang: {user_current_cash}")

    elif msg_content == '!daily':
        daily_cooldown_hours = 12
        amount_to_give = 100

        user_data = await get_user_data(user_id)
        current_cash = user_data["cash"]
        last_claim_time = user_data["last_daily_claim"]

        if last_claim_time:
            time_since_last_claim = datetime.now() - last_claim_time
            if time_since_last_claim < timedelta(hours=daily_cooldown_hours):
                remaining_time = timedelta(hours=daily_cooldown_hours) - time_since_last_claim
                
                total_seconds_left = int(remaining_time.total_seconds())
                hours_left = total_seconds_left // 3600
                minutes_left = (total_seconds_left % 3600) // 60
                seconds_left = total_seconds_left % 60
                
                time_str = []
                if hours_left > 0:
                    time_str.append(f"{hours_left} jam")
                if minutes_left > 0:
                    time_str.append(f"{minutes_left} menit")
                if seconds_left > 0:
                    time_str.append(f"{seconds_left} detik")
                
                if not time_str:
                    time_str = ["sebentar lagi"]

                await message.channel.send(
                    f"⏳ **{message.author.display_name}**, kamu sudah mengklaim daily bonus. "
                    f"Kamu bisa mengklaim lagi dalam **{' dan '.join(time_str)}**."
                )
                print(f"{message.author.name} mencoba daily terlalu cepat. Sisa: {hours_left}j {minutes_left}m {seconds_left}d.")
                return

        new_cash = current_cash + amount_to_give
        current_time = datetime.now()
        
        success_cash = await update_user_cash(user_id, new_cash)
        success_daily = await update_last_daily_claim(user_id, current_time)

        if success_cash and success_daily:
            await message.channel.send(f"🎉 **{message.author.display_name}**, kamu mendapatkan **{amount_to_give} koin harian**! Uangmu sekarang: **{new_cash} koin**.")
            print(f"{message.author.name} berhasil mengklaim daily. Memberi {amount_to_give} koin.")
        else:
            await message.channel.send("Maaf, terjadi kesalahan saat mengupdate uang Anda.")

    elif msg_content.startswith('!givecash '):
        parts = message.content.split()
        if len(parts) == 3 and message.mentions:
            target_user = message.mentions[0]
            try:
                amount = int(parts[2])
                if amount <= 0:
                    await message.channel.send("Jumlah uang yang diberikan harus positif.")
                    return
                if message.author.id == target_user.id:
                    await message.channel.send("Kamu tidak bisa memberikan uang kepada diri sendiri.")
                    return

                sender_data = await get_user_data(user_id)
                sender_current_cash = sender_data["cash"]
                if sender_current_cash < amount:
                    await message.channel.send(f"Uangmu tidak cukup untuk memberikan **{amount} koin**. Uangmu saat ini: {sender_current_cash} koin.")
                    return
                
                new_sender_cash = sender_current_cash - amount
                await update_user_cash(user_id, new_sender_cash)

                target_user_id = target_user.id
                target_data = await get_user_data(target_user_id)
                current_target_cash = target_data["cash"]
                new_target_cash = current_target_cash + amount
                await update_user_cash(target_user_id, new_target_cash)

                await message.channel.send(f"{message.author.mention} berhasil memberikan **{amount} koin** kepada {target_user.mention}! Uang {message.author.display_name}: **{new_sender_cash} koin**. Uang {target_user.display_name}: **{new_target_cash} koin**.")
                print(f"{message.author.name} memberikan {amount} koin kepada {target_user.name}.")

            except ValueError:
                await message.channel.send("Jumlah uang harus berupa angka.")
            except Exception as e:
                await message.channel.send(f"Terjadi kesalahan: {e}")
        else:
            await message.channel.send("Format yang benar: `!givecash @nama_user <jumlah>`")

    elif msg_content.startswith('!addcash '):
        if not await is_admin_cash_adder(user_id):
            await message.channel.send("Maaf, Anda tidak memiliki izin untuk menggunakan perintah ini.")
            return

        parts = message.content.split()
        if len(parts) == 3 and message.mentions:
            target_user = message.mentions[0]
            try:
                amount = int(parts[2])
                if amount <= 0:
                    await message.channel.send("Jumlah uang yang ditambahkan harus positif.")
                    return
                
                target_user_id = target_user.id
                target_data = await get_user_data(target_user_id)
                current_target_cash = target_data["cash"]
                new_target_cash = current_target_cash + amount
                success = await update_user_cash(target_user_id, new_target_cash)

                if success:
                    await message.channel.send(f"Berhasil menambahkan **{amount} koin** kepada {target_user.mention}. Uangnya sekarang: **{new_target_cash} koin**.")
                    print(f"Admin {message.author.name} menambahkan {amount} koin kepada {target_user.name}.")
                else:
                    await message.channel.send("Maaf, terjadi kesalahan saat menambahkan uang.")
            except ValueError:
                await message.channel.send("Jumlah uang harus berupa angka.")
            except Exception as e:
                await message.channel.send(f"Terjadi kesalahan: {e}")
        else:
            await message.channel.send("Format yang benar: `!addcash @nama_user <jumlah>`")

    elif msg_content.startswith('!removecash '):
        if not await is_admin_cash_adder(user_id):
            await message.channel.send("Maaf, Anda tidak memiliki izin untuk menggunakan perintah ini.")
            return

        parts = message.content.split()
        if len(parts) == 3 and message.mentions:
            target_user = message.mentions[0]
            try:
                amount = int(parts[2])
                if amount <= 0:
                    await message.channel.send("Jumlah uang yang dikurangi harus positif.")
                    return
                
                target_user_id = target_user.id
                target_data = await get_user_data(target_user_id)
                current_target_cash = target_data["cash"]
                
                if current_target_cash < amount:
                    await message.channel.send(f"Uang {target_user.display_name} hanya {current_target_cash} koin. Tidak bisa dikurangi sebanyak {amount} koin.")
                    return

                new_target_cash = current_target_cash - amount
                success = await update_user_cash(target_user_id, new_target_cash)

                if success:
                    await message.channel.send(f"Berhasil mengurangi **{amount} koin** dari {target_user.mention}. Uangnya sekarang: **{new_target_cash} koin**.")
                    print(f"Admin {message.author.name} mengurangi {amount} koin dari {target_user.name}.")
                else:
                    await message.channel.send("Maaf, terjadi kesalahan saat mengurangi uang.")
            except ValueError:
                await message.channel.send("Jumlah uang harus berupa angka.")
            except Exception as e:
                await message.channel.send(f"Terjadi kesalahan: {e}")
        else:
            await message.channel.send("Format yang benar: `!removecash @nama_user <jumlah>`")

    elif msg_content == 'ping':
        await message.channel.send('Pong!')
        print(f"Merespons 'ping' dari {message.author.name}")
    elif msg_content == 'halo':
        await message.channel.send(f'Halo juga, {message.author.mention}!')
        print(f"Merespons 'halo' dari {message.author.name}")
    elif msg_content == '!info':
        await message.channel.send("Saya adalah bot sederhana yang dibuat dengan discord.py.")
        print(f"Merespons '!info' dari {message.author.name}")
    
    # --- Perintah Permainan Blackjack ---
    elif msg_content.startswith('!blackjack ') or msg_content.startswith('!bj '):
        parts = msg_content.split()
        if len(parts) < 2:
            await message.channel.send("Format yang benar: `!blackjack <jumlah_taruhan>` atau `!bj <jumlah_taruhan>`. Taruhan harus positif.")
            return
        
        try:
            bet_amount = int(parts[1])
            if bet_amount <= 0:
                await message.channel.send("Jumlah taruhan harus positif.")
                return
        except ValueError:
            await message.channel.send("Jumlah taruhan harus berupa angka.")
            return

        if user_id in active_blackjack_games and active_blackjack_games[user_id].game_active:
            await message.channel.send("Kamu sudah memiliki permainan Blackjack yang sedang berjalan. Klik `✅` atau `🟥`.")
            return
        
        user_data = await get_user_data(user_id)
        current_cash = user_data["cash"]
        if current_cash < bet_amount:
            await message.channel.send(f"Kamu butuh setidaknya **{bet_amount} koin** untuk bermain Blackjack. Uangmu saat ini: {current_cash} koin.")
            return

        new_cash = current_cash - bet_amount
        await update_user_cash(user_id, new_cash)

        game = BlackjackGame(user_id, bet_amount) 
        result = game.start_game()
        active_blackjack_games[user_id] = game

        player_hand_str = game.get_player_hand_str()
        player_score = game._calculate_hand_value(game.player_hand)
        
        dealer_hand_str_revealed = game.get_dealer_hand_str(hidden=False)
        dealer_score_revealed = game._calculate_hand_value(game.dealer_hand)

        if result == "blackjack_player":
            winning_amount = game.bet_amount * 2
            final_cash = new_cash + winning_amount
            await update_user_cash(user_id, final_cash)
            response_message = await message.channel.send(
                f"🎉 **BLACKJACK! Kemenangan Instan!** 🎉\n"
                f"**{message.author.display_name}** memulai permainan Blackjack (taruhan: **{game.bet_amount} koin**).\n"
                f"Kartu Anda: {player_hand_str} (Total: **{player_score}**)\n"
                f"Kartu Dealer: {dealer_hand_str_revealed} (Total: **{dealer_score_revealed}**)\n"
                f"Anda mendapatkan **{winning_amount} koin**! Saldo baru Anda: **{final_cash} koin**."
            )
            del active_blackjack_games[user_id]
        else:
            response_message = await message.channel.send(
                f"♠️♥️♦️♣️ **BLACKJACK DIMULAI!** ♣️♦️♥️♠️\n"
                f"**{message.author.display_name}** bertaruh **{game.bet_amount} koin**.\n"
                f"Kartu Anda: {player_hand_str} (Total: **{player_score}**)\n"
                f"Kartu Dealer: {dealer_hand_str_revealed} (Total: **{dealer_score_revealed}**)\n"
                "Apa langkah Anda selanjutnya? Klik ✅ untuk **HIT** atau 🟥 untuk **STAND**!"
            )
            blackjack_message_to_player[response_message.id] = user_id
            await response_message.add_reaction('✅')
            await response_message.add_reaction('🟥')

    # --- Perintah Permainan Flip Coin (!flipcoin atau !fc) ---
    elif msg_content.startswith('!flipcoin ') or msg_content.startswith('!fc '):
        parts = msg_content.split()
        if len(parts) < 2:
            await message.channel.send("Format yang benar: `!flipcoin <jumlah_taruhan>` atau `!fc <jumlah_taruhan>`. Taruhan harus positif.")
            return

        try:
            bet_amount = int(parts[1])
            if bet_amount <= 0:
                await message.channel.send("Jumlah taruhan harus positif.")
                return
        except ValueError:
            await message.channel.send("Jumlah taruhan harus berupa angka.")
            return
        
        user_data = await get_user_data(user_id)
        current_cash = user_data["cash"]
        if current_cash < bet_amount:
            await message.channel.send(f"Uangmu tidak cukup untuk bertaruh **{bet_amount} koin**. Uangmu saat ini: {current_cash} koin.")
            return

        new_cash_after_bet = current_cash - bet_amount
        await update_user_cash(user_id, new_cash_after_bet)

        game = FlipCoinGame(user_id, bet_amount)
        
        response_message = await message.channel.send(
            f"**{message.author.display_name}** bertaruh **{bet_amount} koin** di Lempar Koin!\n"
            f"Pilih sisi koin: {FLIPCOIN_HEAD_EMOJI} untuk **Kepala** atau {FLIPCOIN_TAIL_EMOJI} untuk **Ekor**."
        )
        active_flipcoin_games[response_message.id] = game
        await response_message.add_reaction(FLIPCOIN_HEAD_EMOJI)
        await response_message.add_reaction(FLIPCOIN_TAIL_EMOJI)

    # --- Perintah Roulette (!roulette atau !rou) ---
    elif msg_content.startswith('!roulette') or msg_content.startswith('!rou'):
        parts = msg_content.split()
        channel_id = message.channel.id
        
        if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() == 'start'):
            print(f"DEBUG: !roulette start command received from {message.author.name} in channel {message.channel.name}")
            # Periksa izin admin untuk memulai roulette
            if not has_required_role(message.author, ALLOWED_SETADMIN_ROLES):
                await message.channel.send("Maaf, hanya admin yang bisa memulai atau mengakhiri permainan Roulette.")
                return

            if channel_id in current_roulette_rounds and current_roulette_rounds[channel_id]["status"] == "betting":
                await message.channel.send("Permainan Roulette sudah aktif di channel ini. Silakan pasang taruhan Anda.")
                return

            round_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(0, 999)) # ID unik untuk putaran
            current_roulette_rounds[channel_id] = {
                "status": "betting",
                "round_id": round_id,
                "message_id": 0, # Akan diisi setelah pesan dikirim
                "bets": {} # {user_id: [taruhan_obj]} -> [taruhan_obj] = {"amount": int, "bet_type": str, "bet_choice": str}
            }

            roulette_info_message = await message.channel.send(
                f"🎰 **ROULETTE BARU DIMULAI!** 🎰\n"
                f"**Putaran ID:** `{round_id}`\n"
                f"**Taruhan dibuka!** Anda bisa pasang taruhan dengan `!bet <jumlah> <jenis_taruhan> <pilihan>`.\n\n"
                f"**Jenis Taruhan (Contoh):**\n"
                f"  `!bet 50 merah` (atau `hitam`)\n"
                f"  `!bet 50 genap` (atau `ganjil`)\n"
                f"  `!bet 50 tinggi` (19-36) (atau `rendah` (1-18))\n"
                f"  `!bet 10 angka 7` (atau angka 0-36)\n"
                f"  `!bet 20 1st12` (1-12) (atau `2nd12`, `3rd12`)\n"
                f"  `!bet 20 col1` (kolom 1) (atau `col2`, `col3`)\n\n"
                f"Taruhan cepat: Klik {ROULETTE_RED_EMOJI} untuk Merah atau {ROULETTE_BLACK_EMOJI} untuk Hitam (default 10 koin)."
            )
            current_roulette_rounds[channel_id]["message_id"] = roulette_info_message.id
            # Tambahkan message_id ke ROULETTE_BET_MESSAGE_TO_USER untuk dilacak reaksinya
            ROULETTE_BET_MESSAGE_TO_USER[roulette_info_message.id] = channel_id
            await roulette_info_message.add_reaction(ROULETTE_RED_EMOJI) # Emoji untuk Merah
            await roulette_info_message.add_reaction(ROULETTE_BLACK_EMOJI) # Emoji untuk Hitam
            
            print(f"Roulette putaran {round_id} dimulai di channel {message.channel.name}.")

        elif len(parts) == 2 and parts[1].lower() == 'spin':
            print(f"DEBUG: !roulette spin command received from {message.author.name} in channel {message.channel.name}")
            # Periksa izin admin untuk mengakhiri roulette
            if not has_required_role(message.author, ALLOWED_SETADMIN_ROLES):
                await message.channel.send("Maaf, hanya admin yang bisa memulai atau mengakhiri permainan Roulette.")
                return

            if channel_id not in current_roulette_rounds or current_roulette_rounds[channel_id]["status"] != "betting":
                await message.channel.send("Tidak ada permainan Roulette yang aktif untuk diputar. Mulai dengan `!roulette start`.")
                return
            
            round_info = current_roulette_rounds[channel_id]
            round_id = round_info["round_id"]
            current_roulette_rounds[channel_id]["status"] = "spinning" # Tandai sebagai spinning

            await message.channel.send("🚫 **NO MORE BETS!** 🚫 Roda berputar... 🎡")
            
            # Hapus reaksi dari pesan pengumuman taruhan
            if round_info["message_id"] != 0:
                try:
                    roulette_msg = await message.channel.fetch_message(round_info["message_id"])
                    await roulette_msg.clear_reactions()
                    del ROULETTE_BET_MESSAGE_TO_USER[roulette_msg.id] # Hapus dari pelacakan pesan
                except discord.NotFound:
                    print(f"Pesan roulette {round_info['message_id']} tidak ditemukan saat clear reactions.")
                except discord.Forbidden:
                    print("Bot tidak memiliki izin untuk menghapus reaksi.")
            
            winning_number = random.choice(list(ROULETTE_NUMBERS.keys()))
            winning_color = ROULETTE_NUMBERS[winning_number]
            winning_parity = 'genap' if winning_number % 2 == 0 and winning_number != 0 else 'ganjil' if winning_number != 0 else 'none'
            winning_half = 'tinggi' if 19 <= winning_number <= 36 else 'rendah' if 1 <= winning_number <= 18 else 'none'

            await message.channel.send(f"⚪ **Angka pemenang: {winning_number} ({winning_color.upper()})!** ⚪")
            print(f"DEBUG: Angka pemenang Roulette: {winning_number} ({winning_color.upper()}).")

            # Proses taruhan
            bets = await get_roulette_bets_for_round(round_id)
            print(f"DEBUG: Ditemukan {len(bets)} taruhan untuk putaran {round_id}.")
            
            total_winnings = {} # {user_id: jumlah_kemenangan_bersih}
            total_lost_to_house = 0 # Untuk melacak uang yang masuk ke bot

            for bet in bets:
                user_id_bet = bet['user_id']
                bet_type = bet['bet_type']
                bet_choice = bet['bet_choice']
                amount = bet['amount']
                
                is_winner = False
                payout_multiplier = 0

                if bet_type == 'number' and str(winning_number) == bet_choice: # Perbandingan string
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['number']
                elif bet_type == 'color' and winning_color == bet_choice:
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['color']
                elif bet_type == 'parity' and winning_parity == bet_choice:
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['parity']
                elif bet_type == 'half' and winning_half == bet_choice:
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['half']
                elif bet_type == 'dozen' and winning_number in ROULETTE_DOZENS.get(bet_choice, []):
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['dozen']
                elif bet_type == 'column' and winning_number in ROULETTE_COLUMNS.get(bet_choice, []):
                    is_winner = True
                    payout_multiplier = ROULETTE_PAYOUTS['column']
                
                if is_winner:
                    winnings = amount + (amount * payout_multiplier) # Taruhan kembali + keuntungan
                    total_winnings[user_id_bet] = total_winnings.get(user_id_bet, 0) + winnings
                    print(f"DEBUG: Taruhan {user_id_bet} ({bet_type}/{bet_choice}) menang {winnings}.")
                else:
                    total_lost_to_house += amount
                    print(f"DEBUG: Taruhan {user_id_bet} ({bet_type}/{bet_choice}) kalah {amount}.")
            
            # Distribusi kemenangan
            winner_mentions = []
            for user_id_winner, winnings_amount in total_winnings.items():
                user_data = await get_user_data(user_id_winner)
                current_cash = user_data["cash"]
                new_cash = current_cash + winnings_amount
                success_update = await update_user_cash(user_id_winner, new_cash)
                
                if success_update:
                    winner_discord_user = await client.fetch_user(user_id_winner)
                    if winner_discord_user:
                        winner_mentions.append(f"🎉 **{winner_discord_user.display_name}** menang **{winnings_amount} koin**! Saldo baru: **{new_cash} koin**.")
                    else:
                        winner_mentions.append(f"🎉 **User ID {user_id_winner}** menang **{winnings_amount} koin**! Saldo baru: **{new_cash} koin**.")
                    print(f"DEBUG: Kemenangan {user_id_winner} di Roulette berhasil diupdate.")
                else:
                    await message.channel.send(f"⚠️ **ERROR:** Gagal update cash untuk pemenang <@{user_id_winner}> di Roulette. Hubungi admin.")
                    print(f"ERROR: Gagal update cash untuk pemenang {user_id_winner} di Roulette.")
            
            if winner_mentions:
                await message.channel.send("--- **HASIL ROULETTE** ---\n" + "\n".join(winner_mentions))
            else:
                await message.channel.send(f"Tidak ada yang menang di putaran ini. Semua taruhan ({total_lost_to_house} koin) menjadi milik rumah.")
            
            # Hapus taruhan dari database
            await clear_roulette_bets(round_id)
            del current_roulette_rounds[channel_id] # Hapus putaran aktif

        else:
            await message.channel.send("Format yang benar: `!roulette start` untuk memulai atau `!roulette spin` untuk memutar roda.")

    # --- Perintah !bet (untuk menempatkan taruhan di Roulette) ---
    elif msg_content.startswith('!bet '):
        parts = message.content.split(' ', 3) # !bet amount type choice
        channel_id = message.channel.id

        if channel_id not in current_roulette_rounds or current_roulette_rounds[channel_id]["status"] != "betting":
            await message.channel.send("Tidak ada putaran Roulette yang aktif di channel ini. Mulai dengan `!roulette start`.")
            return
        
        if len(parts) < 3: # Minimal !bet <amount> <type>
            await message.channel.send("Format taruhan tidak benar. Contoh: `!bet 100 merah` atau `!bet 20 angka 7`.")
            return
        
        try:
            bet_amount = int(parts[1])
            if bet_amount <= 0:
                await message.channel.send("Jumlah taruhan harus positif.")
                return
        except ValueError:
            await message.channel.send("Jumlah taruhan harus berupa angka.")
            return
        
        user_data = await get_user_data(user_id)
        current_cash = user_data["cash"]
        if current_cash < bet_amount:
            await message.channel.send(f"Uangmu tidak cukup untuk bertaruh **{bet_amount} koin**. Uangmu saat ini: {current_cash} koin.")
            return

        bet_type_raw = parts[2].lower()
        bet_choice = parts[3].lower() if len(parts) > 3 else "" # Pilihan taruhan

        valid_bet = False
        parsed_bet_type = None
        parsed_bet_choice = None

        if bet_type_raw in ['merah', 'hitam']:
            parsed_bet_type = 'color'
            parsed_bet_choice = bet_type_raw
            valid_bet = True
        elif bet_type_raw in ['genap', 'ganjil']:
            parsed_bet_type = 'parity'
            parsed_bet_choice = bet_type_raw
            valid_bet = True
        elif bet_type_raw in ['tinggi', 'rendah']:
            parsed_bet_type = 'half'
            parsed_bet_choice = bet_type_raw
            valid_bet = True
        elif bet_type_raw == 'angka':
            try:
                num_choice = int(bet_choice)
                if 0 <= num_choice <= 36:
                    parsed_bet_type = 'number'
                    parsed_bet_choice = str(num_choice)
                    valid_bet = True
            except ValueError:
                pass # Tetap False
        elif bet_type_raw in ['1st12', '2nd12', '3rd12']:
            parsed_bet_type = 'dozen'
            parsed_bet_choice = bet_type_raw
            valid_bet = True
        elif bet_type_raw in ['col1', 'col2', 'col3']:
            parsed_bet_type = 'column'
            parsed_bet_choice = bet_type_raw
            valid_bet = True
        
        if not valid_bet:
            await message.channel.send("Jenis taruhan tidak valid atau pilihan salah. Contoh: `!bet 100 merah`, `!bet 20 angka 7`, `!bet 50 genap`.")
            return

        # Kurangi uang dan simpan taruhan
        new_cash = current_cash - bet_amount
        await update_user_cash(user_id, new_cash)
        
        round_id = current_roulette_rounds[channel_id]["round_id"]
        success_bet = await add_roulette_bet(round_id, user_id, parsed_bet_type, parsed_bet_choice, bet_amount)

        if success_bet:
            # Simpan juga di state lokal untuk mencegah duplikat taruhan emoji
            if user_id not in current_roulette_rounds[channel_id]["bets"]: # Perbaikan: user_id bukan user.id
                current_roulette_rounds[channel_id]["bets"][user_id] = [] # Perbaikan: user_id bukan user.id
            current_roulette_rounds[channel_id]["bets"][user_id].append({"amount": bet_amount, "bet_type": parsed_bet_type, "bet_choice": parsed_bet_choice}) # Perbaikan: user_id

            await message.channel.send(
                f"**{message.author.display_name}** berhasil menempatkan taruhan **{bet_amount} koin** "
                f"pada **{parsed_bet_type.upper()} - {parsed_bet_choice.upper()}**."
                f" Uang Anda sekarang: **{new_cash} koin**."
            )
            print(f"{message.author.name} bertaruh {bet_amount} di roulette: {parsed_bet_type}/{parsed_bet_choice}.")
        else:
            await message.channel.send(f"Gagal menempatkan taruhan. Terjadi kesalahan database.")
            await update_user_cash(user_id, current_cash) # Kembalikan uang jika taruhan gagal masuk DB
            print(f"WARNING: Taruhan {user_id} {bet_amount} di roulette gagal DB, uang dikembalikan.")

# --- Jalankan Bot dengan Token ---
client.run(TOKEN)
