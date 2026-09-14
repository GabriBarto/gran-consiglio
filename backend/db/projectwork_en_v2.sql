-- phpMyAdmin SQL Dump - ENGLISH VERSION
-- Based on projectwork_corretto.sql
-- All table and column names translated to English
--
-- ---------------------------------------------------------------------
-- NOTE (integration pass): this file is the single source of truth for
-- the schema — the Python backend (backend/app/db/) maps to it, it does
-- not generate or replace it. Two small, additive changes were made on
-- top of the original dump to support already-built backend features,
-- clearly marked below with "-- ADDED:" comments. Nothing else was
-- changed. A seed-data section (2 rows per table, 4 for user/store) was
-- appended at the end, as requested.
-- ---------------------------------------------------------------------

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- ADDED: convenience for running this file standalone with `mysql < file`
-- (a plain phpMyAdmin export normally assumes a DB is already selected).
CREATE DATABASE IF NOT EXISTS `toogood` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `toogood`;

-- --------------------------------------------------------
-- Table structure for `user`
-- --------------------------------------------------------

CREATE TABLE `user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  -- ADDED: 'admin' role (license/shop moderation, see routers/admin.py) —
  -- the original dump only had 'client'/'seller'.
  `role` enum('client','seller','admin') NOT NULL,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  -- ADDED: backs the email verification flow (POST /auth/verify-email).
  `email_verified` tinyint(1) NOT NULL DEFAULT 0,
  -- ADDED: surfaced as UserPublic.created_at.
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `store`
-- --------------------------------------------------------

CREATE TABLE `store` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `userId` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `address` varchar(100) NOT NULL,
  `latitude` decimal(10,8) NOT NULL,
  `longitude` decimal(11,8) NOT NULL,
  `phone` varchar(20) NOT NULL,
  `licenseUrl` varchar(255) NOT NULL,
  `verificationStatus` enum('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `openingTime` time NOT NULL,
  `pickupWindowStart` time NOT NULL,
  `pickupWindowEnd` time NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_store_user` (`userId`),
  CONSTRAINT `fk_store_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `box`
-- --------------------------------------------------------

CREATE TABLE `box` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `storeId` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `price` float NOT NULL,
  `creationDate` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `expireDate` timestamp NULL DEFAULT NULL,
  `maxBoxes` int(11) NOT NULL,
  `soldBoxes` int(11) NOT NULL DEFAULT '0',
  `description` varchar(250) NOT NULL,
  `category` varchar(100) NOT NULL,
  `allergens` varchar(250) NOT NULL,
  `pickupWindowStart` time NOT NULL,
  `pickupWindowEnd` time NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_box_store` (`storeId`),
  CONSTRAINT `fk_box_store` FOREIGN KEY (`storeId`) REFERENCES `store` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `cart`
-- --------------------------------------------------------

CREATE TABLE `cart` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `userId` int(11) NOT NULL,
  `storeId` int(11) NOT NULL,
  `status` enum('active','completed') NOT NULL DEFAULT 'active',
  PRIMARY KEY (`id`),
  KEY `fk_cart_user` (`userId`),
  KEY `fk_cart_store` (`storeId`),
  CONSTRAINT `fk_cart_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cart_store` FOREIGN KEY (`storeId`) REFERENCES `store` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `cart_item`
-- --------------------------------------------------------

CREATE TABLE `cart_item` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cartId` int(11) NOT NULL,
  `boxId` int(11) NOT NULL,
  `quantity` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_cartitem_cart` (`cartId`),
  KEY `fk_cartitem_box` (`boxId`),
  CONSTRAINT `fk_cartitem_cart` FOREIGN KEY (`cartId`) REFERENCES `cart` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cartitem_box` FOREIGN KEY (`boxId`) REFERENCES `box` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `orders`
-- --------------------------------------------------------

CREATE TABLE `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `userId` int(11) NOT NULL,
  `storeId` int(11) NOT NULL,
  `totalPrice` float NOT NULL,
  `orderDate` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `state` enum('booked','pickedUp','cancelled','expired') NOT NULL DEFAULT 'booked',
  `pickupWindow` varchar(20) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_order_user` (`userId`),
  KEY `fk_order_store` (`storeId`),
  CONSTRAINT `fk_order_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_order_store` FOREIGN KEY (`storeId`) REFERENCES `store` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `order_item`
-- --------------------------------------------------------

CREATE TABLE `order_item` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `orderId` int(11) NOT NULL,
  `boxId` int(11) NOT NULL,
  `quantity` int(11) NOT NULL,
  `unitPrice` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_orderitem_order` (`orderId`),
  KEY `fk_orderitem_box` (`boxId`),
  CONSTRAINT `fk_orderitem_order` FOREIGN KEY (`orderId`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_orderitem_box` FOREIGN KEY (`boxId`) REFERENCES `box` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `review`
-- --------------------------------------------------------

CREATE TABLE `review` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `orderId` int(11) NOT NULL,
  `userId` int(11) NOT NULL,
  `storeId` int(11) NOT NULL,
  `rating` double NOT NULL,
  `text` varchar(500) NOT NULL,
  `date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_review_order` (`orderId`),
  KEY `fk_review_user` (`userId`),
  KEY `fk_review_store` (`storeId`),
  CONSTRAINT `fk_review_order` FOREIGN KEY (`orderId`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_review_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_review_store` FOREIGN KEY (`storeId`) REFERENCES `store` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Table structure for `notification`
-- --------------------------------------------------------

CREATE TABLE `notification` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `userId` int(11) NOT NULL,
  `type` enum('orderConfirmed','pickupReminder','boxAvailable','reviewRequest','allergenFlagged','other') NOT NULL,
  `text` varchar(100) NOT NULL,
  `isRead` tinyint(1) NOT NULL DEFAULT '0',
  `date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_notification_user` (`userId`),
  CONSTRAINT `fk_notification_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- ADDED: three tables for short-lived auth bookkeeping (refresh-token
-- revocation, email-verification OTPs, password-reset tokens) that used to
-- live in the API process's memory (lost on every restart). Not part of
-- the original dump — deliberately additive, same as the `admin` role and
-- `user.email_verified`/`created_at` columns above. No seed rows: these
-- are always empty until someone actually registers/logs in/resets.
-- --------------------------------------------------------

CREATE TABLE `refresh_token` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `jti` varchar(64) NOT NULL,
  `userId` int(11) NOT NULL,
  `revoked` tinyint(1) NOT NULL DEFAULT 0,
  `expiresAt` timestamp NOT NULL,
  `createdAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `jti` (`jti`),
  KEY `fk_refreshtoken_user` (`userId`),
  CONSTRAINT `fk_refreshtoken_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `email_verification` (
  `userId` int(11) NOT NULL,
  `otp` varchar(6) NOT NULL,
  `expiresAt` timestamp NOT NULL,
  PRIMARY KEY (`userId`),
  CONSTRAINT `fk_emailverification_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `password_reset` (
  `userId` int(11) NOT NULL,
  `jti` varchar(64) NOT NULL,
  `expiresAt` timestamp NOT NULL,
  PRIMARY KEY (`userId`),
  CONSTRAINT `fk_passwordreset_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- ADDED: review moderation support. `review` already existed in the
-- original dump but had no way to enforce "one review per order" at the
-- DB level and no soft-delete flag; `review_report` is a new table for
-- user-submitted flags. Deliberately additive (same spirit as the
-- refresh_token/email_verification/password_reset block above) — no
-- existing column is changed or removed, so it never invalidates the
-- seed data already inserted below.
-- --------------------------------------------------------

ALTER TABLE `review`
  ADD COLUMN `isRemoved` tinyint(1) NOT NULL DEFAULT 0 AFTER `text`,
  ADD UNIQUE KEY `uq_review_order` (`orderId`);

CREATE TABLE `review_report` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `reviewId` int(11) NOT NULL,
  `userId` int(11) NOT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_reviewreport_review_user` (`reviewId`, `userId`),
  KEY `fk_reviewreport_review` (`reviewId`),
  KEY `fk_reviewreport_user` (`userId`),
  CONSTRAINT `fk_reviewreport_review` FOREIGN KEY (`reviewId`) REFERENCES `review` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_reviewreport_user` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Seed data (fake/demo data — no real external data yet).
-- 4 rows for `user` and `store`, 2 rows for every other table.
-- All seed passwords are "Password123" (same argon2 hash reused, see
-- backend/app/security.py — this is throwaway fake data, not a real
-- credential concern).
-- ---------------------------------------------------------------------

INSERT INTO `user` (`id`, `role`, `username`, `email`, `password`, `email_verified`, `created_at`) VALUES
(1, 'admin',  'Admin',               'admin@example.com',              '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', 1, CURRENT_TIMESTAMP),
(2, 'client', 'Cliente Demo',        'cliente.demo@example.com',       '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', 1, CURRENT_TIMESTAMP),
(3, 'seller', 'Vivaio Rossi',        'vivaio.rossi@example.com',       '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', 1, CURRENT_TIMESTAMP),
(4, 'seller', 'Ortofrutta Bianchi',  'ortofrutta.bianchi@example.com', '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', 1, CURRENT_TIMESTAMP);

-- Two branches per seller, to naturally reach 4 rows without inventing
-- extra user accounts (the simple "my shop" API endpoints operate on a
-- vendor's first/primary store — see backend/app/db/repository.py).
INSERT INTO `store` (`id`, `userId`, `name`, `address`, `latitude`, `longitude`, `phone`, `licenseUrl`, `verificationStatus`, `openingTime`, `pickupWindowStart`, `pickupWindowEnd`) VALUES
(1, 3, 'Vivaio Rossi - Centro',            'Via delle Rose 12, Firenze',      43.76960000, 11.25580000, '+39 333 1234567', 'https://fake-bucket.local/licenses/demo-licenza-approvata.pdf',   'approved', '08:00:00', '18:30:00', '19:30:00'),
(2, 3, 'Vivaio Rossi - Succursale Sud',    'Viale Europa 40, Firenze',        43.75000000, 11.24000000, '+39 333 1234568', 'https://fake-bucket.local/licenses/demo-licenza-succursale.pdf',  'pending',  '09:00:00', '17:00:00', '18:00:00'),
(3, 4, 'Ortofrutta Bianchi',               'Corso Italia 5, Bologna',         44.49490000, 11.34260000, '+39 347 7654321', 'https://fake-bucket.local/licenses/demo-licenza-pending.pdf',     'pending',  '07:30:00', '12:30:00', '13:30:00'),
(4, 4, 'Ortofrutta Bianchi - Mercato',     'Piazza Maggiore 1, Bologna',      44.49380000, 11.34290000, '+39 347 7654322', 'https://fake-bucket.local/licenses/demo-licenza-rejected.pdf',    'rejected', '06:30:00', '11:00:00', '12:00:00');

INSERT INTO `box` (`id`, `storeId`, `name`, `price`, `expireDate`, `maxBoxes`, `soldBoxes`, `description`, `category`, `allergens`, `pickupWindowStart`, `pickupWindowEnd`) VALUES
(1, 1, 'Box Frutta Mista',   4.99, '2026-09-13 20:00:00', 10, 3, 'Cassetta di frutta di stagione in eccedenza',  'Frutta e Verdura', 'Nessuno',                     '18:30:00', '19:30:00'),
(2, 3, 'Box Pane e Dolci',   3.50, '2026-09-13 14:00:00',  8, 5, 'Pane e prodotti da forno del giorno invenduti', 'Panetteria',        'Glutine, Uova, Latte',        '12:30:00', '13:30:00');

INSERT INTO `cart` (`id`, `userId`, `storeId`, `status`) VALUES
(1, 2, 1, 'active'),
(2, 2, 3, 'completed');

INSERT INTO `cart_item` (`id`, `cartId`, `boxId`, `quantity`) VALUES
(1, 1, 1, 2),
(2, 2, 2, 1);

INSERT INTO `orders` (`id`, `userId`, `storeId`, `totalPrice`, `state`, `pickupWindow`) VALUES
(1, 2, 3, 3.50, 'pickedUp', '12:30-13:30'),
(2, 2, 1, 9.98, 'pickedUp', '18:30-19:30');

INSERT INTO `order_item` (`id`, `orderId`, `boxId`, `quantity`, `unitPrice`) VALUES
(1, 1, 2, 1, 3.50),
(2, 2, 1, 2, 4.99);

INSERT INTO `review` (`id`, `orderId`, `userId`, `storeId`, `rating`, `text`) VALUES
(1, 1, 2, 3, 4.5, 'Pane buonissimo e ancora fresco, consigliatissimo!'),
(2, 2, 2, 1, 5.0, 'Frutta freschissima, tornerò sicuramente!');

INSERT INTO `notification` (`id`, `userId`, `type`, `text`, `isRead`) VALUES
(1, 2, 'orderConfirmed',  'Il tuo ordine da Ortofrutta Bianchi è confermato.',              1),
(2, 2, 'pickupReminder',  'Ricorda di ritirare il tuo box da Vivaio Rossi entro le 19:30.', 0);

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
