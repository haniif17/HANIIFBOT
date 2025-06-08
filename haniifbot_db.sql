-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Waktu pembuatan: 08 Jun 2025 pada 11.01
-- Versi server: 10.4.32-MariaDB
-- Versi PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `haniifbot_db`
--

-- --------------------------------------------------------

--
-- Struktur dari tabel `bot_admins`
--

CREATE TABLE `bot_admins` (
  `user_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `bot_admins`
--

INSERT INTO `bot_admins` (`user_id`) VALUES
(941519181554258011);

-- --------------------------------------------------------

--
-- Struktur dari tabel `events`
--

CREATE TABLE `events` (
  `event_id` int(11) NOT NULL,
  `event_type` varchar(50) NOT NULL,
  `description` varchar(255) NOT NULL,
  `bet_cost` int(11) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'open',
  `winning_choice` varchar(20) DEFAULT NULL,
  `message_id` bigint(20) DEFAULT NULL,
  `channel_id` bigint(20) DEFAULT NULL,
  `created_by` bigint(20) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `events`
--

INSERT INTO `events` (`event_id`, `event_type`, `description`, `bet_cost`, `status`, `winning_choice`, `message_id`, `channel_id`, `created_by`, `created_at`) VALUES
(1, 'bola', 'Adu Ayam', 1000, 'finished', 'merah', 1381188124503179354, 1381155373742035088, 941519181554258011, '2025-06-08 15:28:33'),
(2, 'bola', 'merahbiru', 1000, 'finished', 'biru', 1381192364311187600, 1381155373742035088, 941519181554258011, '2025-06-08 15:45:23'),
(3, 'bola', 'MerahBiru', 1000, 'finished', 'merah', 1381193838709706833, 1381155373742035088, 941519181554258011, '2025-06-08 15:51:15'),
(23, 'bola', 'merah atau biru', 1000, 'finished', 'merah', 1381188506457604127, 1381155373742035088, 941519181554258011, '2025-06-08 15:30:04');

-- --------------------------------------------------------

--
-- Struktur dari tabel `event_participants`
--

CREATE TABLE `event_participants` (
  `participant_id` int(11) NOT NULL,
  `event_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `choice` varchar(20) NOT NULL,
  `joined_at` datetime NOT NULL DEFAULT current_timestamp(),
  `paid_amount` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `event_participants`
--

INSERT INTO `event_participants` (`participant_id`, `event_id`, `user_id`, `choice`, `joined_at`, `paid_amount`) VALUES
(1, 3, 941519181554258011, 'merah', '2025-06-08 15:51:20', 1000);

-- --------------------------------------------------------

--
-- Struktur dari tabel `users_cash`
--

CREATE TABLE `users_cash` (
  `user_id` bigint(20) NOT NULL,
  `cash` int(11) NOT NULL DEFAULT 0,
  `last_daily_claim` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `users_cash`
--

INSERT INTO `users_cash` (`user_id`, `cash`, `last_daily_claim`) VALUES
(743269440187007016, 90000, NULL),
(758879838240768021, 100, '2025-06-08 14:47:18'),
(941519181554258011, 1000, '2025-06-08 14:40:10');

--
-- Indexes for dumped tables
--

--
-- Indeks untuk tabel `bot_admins`
--
ALTER TABLE `bot_admins`
  ADD PRIMARY KEY (`user_id`);

--
-- Indeks untuk tabel `events`
--
ALTER TABLE `events`
  ADD PRIMARY KEY (`event_id`);

--
-- Indeks untuk tabel `event_participants`
--
ALTER TABLE `event_participants`
  ADD PRIMARY KEY (`participant_id`),
  ADD UNIQUE KEY `event_id` (`event_id`,`user_id`);

--
-- Indeks untuk tabel `users_cash`
--
ALTER TABLE `users_cash`
  ADD PRIMARY KEY (`user_id`);

--
-- AUTO_INCREMENT untuk tabel yang dibuang
--

--
-- AUTO_INCREMENT untuk tabel `events`
--
ALTER TABLE `events`
  MODIFY `event_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=24;

--
-- AUTO_INCREMENT untuk tabel `event_participants`
--
ALTER TABLE `event_participants`
  MODIFY `participant_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- Ketidakleluasaan untuk tabel pelimpahan (Dumped Tables)
--

--
-- Ketidakleluasaan untuk tabel `event_participants`
--
ALTER TABLE `event_participants`
  ADD CONSTRAINT `event_participants_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `events` (`event_id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
