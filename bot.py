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

# --- DAFTAR ID ROLE YANG DIIZINKAN UNTUK MENGGUNAKAN !setadmin (dan !createevent, !endevent) ---
ALLOWED_SETADMIN_ROLES = [
    1381168735112659015 # Ini adalah Role ID yang Anda berikan
]
if not ALLOWED_SETADMIN_ROLES:
    print("PERINGATAN: ALLOWED_SETADMIN_ROLES kosong. Tidak ada role yang bisa menggunakan !setadmin, !createevent, !endevent.")

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
        elif dealer_score > player_score:
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

# --- Event Game Constants ---
# Untuk event bola
EVENT_TEAM_RED_EMOJI = '🔴'
EVENT_TEAM_BLUE_EMOJI = '🔵' # Atau bisa '🟦' atau '🔷'
active_event_messages = {} # {message_id: event_id}


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

# --- Fungsi untuk Manajemen Admin Bot (Termasuk Event) ---
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

# --- Fungsi untuk Manajemen Event ---
async def create_event_db(event_type: str, event_id: int, bet_cost: int, description: str, created_by: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO events (event_id, event_type, description, bet_cost, created_by) VALUES (%s, %s, %s, %s, %s)",
            (event_id, event_type, description, bet_cost, created_by)
        )
        conn.commit()
        return True
    except Error as e:
        print(f"ERROR CREATE EVENT: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def get_event_by_id(event_id: int) -> dict:
    conn = get_db_connection()
    if conn is None: return None
    cursor = conn.cursor(dictionary=True) # Untuk mendapatkan hasil sebagai dictionary
    try:
        cursor.execute("SELECT * FROM events WHERE event_id = %s", (event_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"ERROR GET EVENT BY ID: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def update_event_message_info(event_id: int, message_id: int, channel_id: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE events SET message_id = %s, channel_id = %s WHERE event_id = %s",
            (message_id, channel_id, event_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"ERROR UPDATE EVENT MESSAGE INFO: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def get_open_events() -> list[dict]:
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'open'")
        return cursor.fetchall()
    except Error as e:
        print(f"ERROR GET OPEN EVENTS: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def add_participant_to_event(event_id: int, user_id: int, choice: str, paid_amount: int) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO event_participants (event_id, user_id, choice, paid_amount) VALUES (%s, %s, %s, %s)",
            (event_id, user_id, choice, paid_amount)
        )
        conn.commit()
        return True
    except Error as e:
        if e.errno == 1062: # Duplicate entry for UNIQUE constraint
            print(f"User {user_id} sudah terdaftar di event {event_id}.")
            return False
        print(f"ERROR ADD PARTICIPANT: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def get_event_participants(event_id: int) -> list[dict]:
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, choice, paid_amount FROM event_participants WHERE event_id = %s", (event_id,))
        return cursor.fetchall()
    except Error as e:
        print(f"ERROR GET PARTICIPANTS: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def end_event_db(event_id: int, winning_choice: str) -> bool:
    conn = get_db_connection()
    if conn is None: return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE events SET status = 'finished', winning_choice = %s WHERE event_id = %s",
            (winning_choice, event_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"ERROR END EVENT: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- Event Bot Siap ---
@client.event
async def on_ready():
    print(f'Bot {client.user} berhasil login!')
    print(f'ID Bot: {client.user.id}')
    await client.change_presence(activity=discord.Game(name="main !blackjack, !flipcoin, !daily, dan event!"))
    print("Bot siap melayani perintah!")

# --- Event Bot Menerima Reaksi (Diperbarui untuk Flip Coin dan Event Bola) ---
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
            # await reaction.message.clear_reactions() # Hapus semua reaksi setelah aksi? (Opsional, jika hanya 1 aksi)
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
                # Pastikan message_id lama dihapus dan yang baru ditambahkan
                del blackjack_message_to_player[reaction.message.id] # Hapus pesan lama
                blackjack_message_to_player[new_message.id] = user.id # Tambahkan pesan baru
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
                user_data = await get_user_data(user.id) # Perbaikan: Pastikan user_data diambil
                final_cash = user_data["cash"] + (bet_amount * 2)
                await update_user_cash(user.id, final_cash)
                response_message = (
                    f"**{user.display_name} memutuskan untuk STAND!**\n"
                    f"Kartu Anda: {player_hand_str} (Total: {player_score})\n"
                    f"Kartu Dealer: {dealer_hand_str_revealed} (Total: {dealer_score})\n"
                    f"🎉 **DEALER BUST! Anda menang {bet_amount * 2} koin!** 🎉"
                )
            elif result == "player_win":
                user_data = await get_user_data(user.id) # Perbaikan: Pastikan user_data diambil
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
                user_data = await get_user_data(user.id) # Perbaikan di sini
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
            del blackjack_message_to_player[reaction.message.id] # Hapus pesan lama

    # --- Logika untuk Flip Coin ---
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
            del active_flipcoin_games[reaction.message.id]
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

        game.player_choice = user_choice_str
        game.game_active = False # Game selesai setelah pilihan diterima

        # Lakukan lemparan koin
        coin_sides = ['kepala', 'ekor']
        coin_result = random.choice(coin_sides)
        
        result_message = ""
        user_data = await get_user_data(user.id) # Perbaikan: Pastikan user_data diambil
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
            final_cash = current_cash # Uang sudah dikurangi di awal, tidak perlu pengurangan lagi
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

    # --- Logika untuk Event Bola (BARU) ---
    # Ini adalah bagian where partisipan bergabung ke event dengan reaksi
    else: # Jika reaksi bukan untuk Blackjack atau Flipcoin, cek untuk event bola
        conn = get_db_connection()
        if conn is None: return

        cursor = conn.cursor(dictionary=True)
        try:
            # Ambil event yang pesannya cocok dengan reaksi
            cursor.execute("SELECT * FROM events WHERE message_id = %s AND status = 'open'", (reaction.message.id,))
            event = cursor.fetchone()

            if event:
                event_id = event['event_id']
                bet_cost = event['bet_cost']
                
                # Cek apakah user sudah berpartisipasi
                cursor.execute("SELECT * FROM event_participants WHERE event_id = %s AND user_id = %s", (event_id, user.id))
                already_joined = cursor.fetchone()
                if already_joined:
                    await reaction.message.channel.send(f"**{user.display_name}**, Anda sudah berpartisipasi dalam event ini.")
                    try:
                        await reaction.message.remove_reaction(reaction.emoji, user)
                    except discord.Forbidden: pass
                    return

                # Tentukan pilihan berdasarkan emoji
                user_choice = None
                if str(reaction.emoji) == EVENT_TEAM_RED_EMOJI:
                    user_choice = 'merah'
                elif str(reaction.emoji) == EVENT_TEAM_BLUE_EMOJI:
                    user_choice = 'biru'
                else: # Emoji bukan pilihan event
                    try:
                        await reaction.message.remove_reaction(reaction.emoji, user)
                    except discord.Forbidden: pass
                    return

                # Cek saldo user
                user_data = await get_user_data(user.id) # Perbaikan: Pastikan user_data diambil
                current_cash = user_data["cash"]
                if current_cash < bet_cost:
                    await reaction.message.channel.send(f"**{user.display_name}**, uang Anda tidak cukup ({current_cash} koin). Event ini membutuhkan {bet_cost} koin.")
                    try:
                        await reaction.message.remove_reaction(reaction.emoji, user)
                    except discord.Forbidden: pass
                    return
                
                # Kurangi uang dan catat partisipasi
                new_cash = current_cash - bet_cost
                await update_user_cash(user.id, new_cash)
                success_participant = await add_participant_to_event(event_id, user.id, user_choice, bet_cost)

                if success_participant:
                    await reaction.message.channel.send(
                        f"**{user.display_name}** berhasil bergabung ke Event ID `{event_id}` ({event['description']}) dengan memilih **{user_choice.upper()}** dan membayar **{bet_cost} koin**."
                        f" Uang Anda sekarang: **{new_cash} koin**."
                    )
                    print(f"{user.name} bergabung event {event_id} dengan pilihan {user_choice}.")
                else:
                    await reaction.message.channel.send(f"**{user.display_name}**, gagal bergabung ke event. Mungkin Anda sudah terdaftar atau terjadi kesalahan.")
                
                try: # Hapus reaksi user setelah berhasil bergabung
                    await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.Forbidden: pass

        except Error as e:
            print(f"ERROR ON REACTION ADD (EVENT): {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()


# --- Event Bot Menerima Pesan ---
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    msg_content = message.content.lower()
    user_id = message.author.id

    # --- Fungsi Pengecekan Role Izin !setadmin ---
    # Fungsi ini perlu didefinisikan di level global agar bisa diakses oleh on_message
    def has_required_role(member: discord.Member, allowed_roles: list[int]) -> bool:
        """Memeriksa apakah member memiliki salah satu dari role yang diizinkan."""
        if not member.guild: # Tidak bisa memeriksa role di DM
            return False
        if not allowed_roles:
            return False
        for role in member.roles:
            if role.id in allowed_roles:
                return True
        return False

    # --- Perintah !setadmin ---
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

    # --- Perintah !balance ---
    elif msg_content == '!balance':
        user_data = await get_user_data(user_id)
        user_current_cash = user_data["cash"]
        await message.channel.send(f"{message.author.mention}, uang kamu saat ini: **{user_current_cash} koin**.")
        print(f"Merespons '!balance' dari {message.author.name}. Uang: {user_current_cash}")

    # --- Perintah !daily ---
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

    # --- Perintah !createevent (Admin only) ---
    # Format: !createevent <event_type> <event_id_custom> <bet_cost> <description...>
    # Contoh: !createevent bola 1 1000 Pertandingan UEFA Nations League: Portugal VS Spanyol
    elif msg_content.startswith('!createevent '):
        if not message.guild:
            await message.channel.send("Perintah ini hanya bisa digunakan di dalam server Discord.")
            return
        # Perbaikan: Memeriksa role admin untuk event
        if not has_required_role(message.author, ALLOWED_SETADMIN_ROLES):
            await message.channel.send("Maaf, Anda tidak memiliki role yang diperlukan untuk membuat event.")
            return

        parts = message.content.split(' ', 4) # Split hingga 4 bagian: cmd, type, id, cost, desc
        if len(parts) < 5:
            await message.channel.send("Format yang benar: `!createevent <tipe_event> <ID_event_custom> <biaya_bet> <deskripsi_event>`")
            await message.channel.send("Contoh: `!createevent bola 1 1000 Pertandingan UEFA Nations League: Portugal VS Spanyol`")
            return
        
        event_type = parts[1].lower()
        try:
            event_id_custom = int(parts[2])
            bet_cost = int(parts[3])
            description = parts[4]
            if bet_cost <= 0:
                await message.channel.send("Biaya bet harus positif.")
                return
        except ValueError:
            await message.channel.send("ID event dan biaya bet harus berupa angka. Deskripsi event tidak boleh kosong.")
            return
        
        # Cek apakah event_id_custom sudah ada
        existing_event = await get_event_by_id(event_id_custom)
        if existing_event:
            await message.channel.send(f"Event dengan ID `{event_id_custom}` sudah ada. Gunakan ID lain atau akhiri event yang sudah ada.")
            return

        # Simpan event ke database
        success = await create_event_db(event_type, event_id_custom, bet_cost, description, user_id)
        if success:
            event_message_text = (
                f"📢 **EVENT BARU TELAH DIBUAT!** 📢\n"
                f"**ID Event:** `{event_id_custom}`\n"
                f"**Tipe:** {event_type.upper()}\n"
                f"**Deskripsi:** {description}\n"
                f"**Biaya Partisipasi:** **{bet_cost} koin**\n\n"
                f"Untuk berpartisipasi, klik {EVENT_TEAM_RED_EMOJI} (Merah) atau {EVENT_TEAM_BLUE_EMOJI} (Biru) di bawah pesan ini."
            )
            event_message = await message.channel.send(event_message_text)
            
            # Simpan message_id dan channel_id ke database untuk event ini
            await update_event_message_info(event_id_custom, event_message.id, message.channel.id)

            await event_message.add_reaction(EVENT_TEAM_RED_EMOJI)
            await event_message.add_reaction(EVENT_TEAM_BLUE_EMOJI)
            
            await message.channel.send(f"Event `{event_id_custom}` berhasil dibuat!")
            print(f"Event {event_id_custom} ({event_type}) dibuat oleh {message.author.name}.")
        else:
            await message.channel.send("Gagal membuat event. Terjadi kesalahan database.")

    # --- Perintah !endevent (Admin only) ---
    # Format: !endevent <event_id> <winning_choice>
    # Contoh: !endevent 1 merah
    elif msg_content.startswith('!endevent '):
        if not message.guild:
            await message.channel.send("Perintah ini hanya bisa digunakan di dalam server Discord.")
            return
        if not has_required_role(message.author, ALLOWED_SETADMIN_ROLES):
            await message.channel.send("Maaf, Anda tidak memiliki role yang diperlukan untuk mengakhiri event.")
            return

        parts = message.content.split()
        if len(parts) != 3:
            await message.channel.send("Format yang benar: `!endevent <ID_event> <merah/biru>`")
            return
        
        try:
            event_id = int(parts[1])
            winning_choice = parts[2].lower()
            if winning_choice not in ['merah', 'biru']:
                await message.channel.send("Pilihan pemenang harus 'merah' atau 'biru'.")
                return
        except ValueError:
            await message.channel.send("ID event harus berupa angka.")
            return

        event_data_for_distro = await get_event_by_id(event_id) # Ambil data event
        if not event_data_for_distro:
            await message.channel.send(f"Event dengan ID `{event_id}` tidak ditemukan.")
            return
        if event_data_for_distro['status'] == 'finished':
            await message.channel.send(f"Event dengan ID `{event_id}` sudah selesai.")
            return
        if event_data_for_distro['status'] == 'closed':
            await message.channel.send(f"Event dengan ID `{event_id}` sudah ditutup pendaftarannya. Mohon tunggu proses pembagian hadiah.")
            return
        
        # Akhiri event di database
        success = await end_event_db(event_id, winning_choice)
        if success:
            await message.channel.send(f"Event `{event_id}` berhasil diakhiri dengan pemenang **{winning_choice.upper()}**!")
            print(f"Event {event_id} diakhiri oleh {message.author.name} dengan pemenang {winning_choice}.")
            
            # Mulai proses pembagian hadiah
            await distribute_event_prizes(event_data_for_distro, winning_choice, message.channel)
            
        else:
            await message.channel.send("Gagal mengakhiri event. Terjadi kesalahan database.")

    # --- Perintah !listevent ---
    elif msg_content == '!listevent':
        open_events = await get_open_events()
        if not open_events:
            await message.channel.send("Tidak ada event yang sedang berjalan saat ini.")
            return
        
        event_list_message = "✨ **DAFTAR EVENT YANG SEDANG BERJALAN** ✨\n\n"
        for event in open_events:
            event_list_message += (
                f"**ID:** `{event['event_id']}`\n"
                f"**Tipe:** {event['event_type'].upper()}\n"
                f"**Deskripsi:** {event['description']}\n"
                f"**Biaya Partisipasi:** {event['bet_cost']} koin\n"
                f"**Dibuat oleh:** <@{event['created_by']}> pada {event['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"----------------------------------------\n"
            )
        await message.channel.send(event_list_message)
        print(f"{message.author.name} melihat daftar event.")

# --- Fungsi Pembagian Hadiah Event ---
async def distribute_event_prizes(event: dict, winning_choice: str, channel: discord.TextChannel):
    conn = get_db_connection()
    if conn is None:
        await channel.send(f"Gagal membagikan hadiah event `{event['event_id']}`: Koneksi database gagal.")
        return

    cursor = conn.cursor(dictionary=True)
    try:
        participants = await get_event_participants(event['event_id'])
        
        total_pot = 0
        winners = []

        for p in participants:
            total_pot += p['paid_amount']
            if p['choice'] == winning_choice:
                winners.append(p)

        if not winners:
            await channel.send(
                f"Event `{event['event_id']}` selesai. "
                f"Tidak ada pemenang untuk pilihan **{winning_choice.upper()}**. "
                f"Total pot **{total_pot} koin** akan menjadi milik bot." # Menjelaskan ke mana uang pergi
            )
            return
        
        prize_pool = total_pot
        prize_per_winner = prize_pool / len(winners)

        winner_mentions = []
        for winner in winners:
            user_id = winner['user_id']
            user_data = await get_user_data(user_id) # Ambil saldo terbaru
            current_cash = user_data["cash"]
            new_cash = current_cash + int(prize_per_winner) # Tambah hadiah, bulatkan ke bawah
            await update_user_cash(user_id, new_cash)
            
            winner_user = await client.fetch_user(user_id) # Ambil objek user dari Discord
            if winner_user:
                winner_mentions.append(winner_user.mention) # Menggunakan mention
            else:
                winner_mentions.append(f"User ID {user_id}")

        await channel.send(
            f"🏆 **HADIAH EVENT `{event['event_id']}` DIBAGIKAN!** 🏆\n"
            f"Event **'{event['description']}'** telah berakhir!\n"
            f"Pilihan yang menang adalah **{winning_choice.upper()}**.\n"
            f"Total pot: **{total_pot} koin**.\n"
            f"Jumlah pemenang: **{len(winners)} orang**.\n"
            f"Setiap pemenang mendapatkan: **{int(prize_per_winner)} koin**.\n"
            f"Pemenang: {', '.join(winner_mentions)}!"
        )
        print(f"Hadiah event {event['event_id']} dibagikan. Pemenang: {', '.join(winner_mentions)}.")

    except Error as e:
        print(f"ERROR DISTRIBUTE PRIZES: {e}")
        await channel.send(f"Terjadi kesalahan saat membagikan hadiah event `{event['event_id']}`.")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- Jalankan Bot dengan Token ---
client.run(TOKEN)