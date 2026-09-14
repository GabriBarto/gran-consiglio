-- PostgreSQL version of backend/db/projectwork_en_v2.sql, per l'uso con Neon.
-- Nomi di tabelle/colonne (incluso il camelCase) corrispondono esattamente
-- a backend/app/db/models.py, che li referenzia via mapped_column("nomeColonna", ...).
--
-- Come eseguirlo su Neon:
--   1) Dashboard Neon -> il tuo progetto -> "SQL Editor" -> incolla ed esegui questo file.
--   2) In alternativa, da terminale (se hai psql installato):
--        psql "postgresql://USER:PASSWORD@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require" -f projectwork_postgres.sql
--      (usa l'host DIRETTO, senza "-pooler", per i DDL/transazioni lunghe)

BEGIN;

-- ---------------------------------------------------------------------
-- Tipi enum (SQLAlchemy li mappa come ENUM nativi Postgres — i nomi
-- corrispondono all'argomento name= di ogni Enum(...) in models.py)
-- ---------------------------------------------------------------------
CREATE TYPE user_role AS ENUM ('client', 'seller', 'admin');
CREATE TYPE verification_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE cart_status AS ENUM ('active', 'completed');
CREATE TYPE order_state AS ENUM ('booked', 'pickedUp', 'cancelled', 'expired');

-- --------------------------------------------------------
CREATE TABLE "user" (
  id SERIAL PRIMARY KEY,
  role user_role NOT NULL,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(100) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- --------------------------------------------------------
CREATE TABLE store (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  name VARCHAR(50) NOT NULL,
  address VARCHAR(100) NOT NULL,
  latitude DECIMAL(10,8) NOT NULL,
  longitude DECIMAL(11,8) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  "licenseUrl" VARCHAR(255) NOT NULL,
  "verificationStatus" verification_status NOT NULL DEFAULT 'pending',
  "openingTime" TIME NOT NULL,
  "pickupWindowStart" TIME NOT NULL,
  "pickupWindowEnd" TIME NOT NULL
);
CREATE INDEX fk_store_user ON store ("userId");

-- --------------------------------------------------------
CREATE TABLE box (
  id SERIAL PRIMARY KEY,
  "storeId" INTEGER NOT NULL REFERENCES store(id) ON DELETE CASCADE,
  name VARCHAR(50) NOT NULL,
  price DOUBLE PRECISION NOT NULL,
  "creationDate" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "expireDate" TIMESTAMP DEFAULT NULL,
  "maxBoxes" INTEGER NOT NULL,
  "soldBoxes" INTEGER NOT NULL DEFAULT 0,
  description VARCHAR(250) NOT NULL,
  category VARCHAR(100) NOT NULL,
  allergens VARCHAR(250) NOT NULL,
  "pickupWindowStart" TIME NOT NULL,
  "pickupWindowEnd" TIME NOT NULL
);
CREATE INDEX fk_box_store ON box ("storeId");

-- --------------------------------------------------------
CREATE TABLE cart (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  "storeId" INTEGER NOT NULL REFERENCES store(id) ON DELETE CASCADE,
  status cart_status NOT NULL DEFAULT 'active'
);
CREATE INDEX fk_cart_user ON cart ("userId");
CREATE INDEX fk_cart_store ON cart ("storeId");

-- --------------------------------------------------------
CREATE TABLE cart_item (
  id SERIAL PRIMARY KEY,
  "cartId" INTEGER NOT NULL REFERENCES cart(id) ON DELETE CASCADE,
  "boxId" INTEGER NOT NULL REFERENCES box(id) ON DELETE CASCADE,
  quantity INTEGER NOT NULL
);
CREATE INDEX fk_cartitem_cart ON cart_item ("cartId");
CREATE INDEX fk_cartitem_box ON cart_item ("boxId");

-- --------------------------------------------------------
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES "user"(id),
  "storeId" INTEGER NOT NULL REFERENCES store(id),
  "totalPrice" DOUBLE PRECISION NOT NULL,
  "orderDate" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  state order_state NOT NULL DEFAULT 'booked',
  "pickupWindow" VARCHAR(20) NOT NULL
);
CREATE INDEX fk_order_user ON orders ("userId");
CREATE INDEX fk_order_store ON orders ("storeId");

-- --------------------------------------------------------
CREATE TABLE order_item (
  id SERIAL PRIMARY KEY,
  "orderId" INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  "boxId" INTEGER NOT NULL REFERENCES box(id),
  quantity INTEGER NOT NULL,
  "unitPrice" DOUBLE PRECISION NOT NULL
);
CREATE INDEX fk_orderitem_order ON order_item ("orderId");
CREATE INDEX fk_orderitem_box ON order_item ("boxId");

-- -------------------------------------------------------- (non ancora usate da endpoint, mantenute per parità)
CREATE TABLE review (
  id SERIAL PRIMARY KEY,
  "orderId" INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  "userId" INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  "storeId" INTEGER NOT NULL REFERENCES store(id) ON DELETE CASCADE,
  rating DOUBLE PRECISION NOT NULL,
  text VARCHAR(500) NOT NULL,
  date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX fk_review_order ON review ("orderId");
CREATE INDEX fk_review_user ON review ("userId");
CREATE INDEX fk_review_store ON review ("storeId");

CREATE TABLE notification (
  id SERIAL PRIMARY KEY,
  "userId" INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  type VARCHAR(30) NOT NULL,
  text VARCHAR(100) NOT NULL,
  "isRead" BOOLEAN NOT NULL DEFAULT FALSE,
  date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX fk_notification_user ON notification ("userId");

-- --------------------------------------------------------
-- Tabelle di supporto auth (refresh token, verifica email, reset password)
-- --------------------------------------------------------
CREATE TABLE refresh_token (
  id SERIAL PRIMARY KEY,
  jti VARCHAR(64) NOT NULL UNIQUE,
  "userId" INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  "expiresAt" TIMESTAMP NOT NULL,
  "createdAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX fk_refreshtoken_user ON refresh_token ("userId");

CREATE TABLE email_verification (
  "userId" INTEGER PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  otp VARCHAR(6) NOT NULL,
  "expiresAt" TIMESTAMP NOT NULL
);

CREATE TABLE password_reset (
  "userId" INTEGER PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  jti VARCHAR(64) NOT NULL,
  "expiresAt" TIMESTAMP NOT NULL
);

-- ---------------------------------------------------------------------
-- Dati demo (stesso seed dell'originale — 4 righe user/store, 2 per il resto)
-- Password di tutti gli utenti demo: "Password123"
-- ---------------------------------------------------------------------
INSERT INTO "user" (id, role, username, email, password, email_verified, created_at) VALUES
(1, 'admin',  'Admin',               'admin@example.com',              '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', TRUE, CURRENT_TIMESTAMP),
(2, 'client', 'Cliente Demo',        'cliente.demo@example.com',       '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', TRUE, CURRENT_TIMESTAMP),
(3, 'seller', 'Vivaio Rossi',        'vivaio.rossi@example.com',       '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', TRUE, CURRENT_TIMESTAMP),
(4, 'seller', 'Ortofrutta Bianchi',  'ortofrutta.bianchi@example.com', '$argon2id$v=19$m=65536,t=3,p=4$DiGEMAbAOKdUSqmVcq713g$hSAHeeHqAw/ruvopL59CQu1PjVzLs30XyJz9+kVA6D0', TRUE, CURRENT_TIMESTAMP);
SELECT setval(pg_get_serial_sequence('"user"', 'id'), (SELECT MAX(id) FROM "user"));

INSERT INTO store (id, "userId", name, address, latitude, longitude, phone, "licenseUrl", "verificationStatus", "openingTime", "pickupWindowStart", "pickupWindowEnd") VALUES
(1, 3, 'Vivaio Rossi - Centro',            'Via delle Rose 12, Firenze',      43.76960000, 11.25580000, '+39 333 1234567', 'https://fake-bucket.local/licenses/demo-licenza-approvata.pdf',   'approved', '08:00:00', '18:30:00', '19:30:00'),
(2, 3, 'Vivaio Rossi - Succursale Sud',    'Viale Europa 40, Firenze',        43.75000000, 11.24000000, '+39 333 1234568', 'https://fake-bucket.local/licenses/demo-licenza-succursale.pdf',  'pending',  '09:00:00', '17:00:00', '18:00:00'),
(3, 4, 'Ortofrutta Bianchi',               'Corso Italia 5, Bologna',         44.49490000, 11.34260000, '+39 347 7654321', 'https://fake-bucket.local/licenses/demo-licenza-pending.pdf',     'pending',  '07:30:00', '12:30:00', '13:30:00'),
(4, 4, 'Ortofrutta Bianchi - Mercato',     'Piazza Maggiore 1, Bologna',      44.49380000, 11.34290000, '+39 347 7654322', 'https://fake-bucket.local/licenses/demo-licenza-rejected.pdf',    'rejected', '06:30:00', '11:00:00', '12:00:00');
SELECT setval(pg_get_serial_sequence('store', 'id'), (SELECT MAX(id) FROM store));

INSERT INTO box (id, "storeId", name, price, "expireDate", "maxBoxes", "soldBoxes", description, category, allergens, "pickupWindowStart", "pickupWindowEnd") VALUES
(1, 1, 'Box Frutta Mista',   4.99, '2026-09-13 20:00:00', 10, 3, 'Cassetta di frutta di stagione in eccedenza',  'Frutta e Verdura', 'Nessuno',                     '18:30:00', '19:30:00'),
(2, 3, 'Box Pane e Dolci',   3.50, '2026-09-13 14:00:00',  8, 5, 'Pane e prodotti da forno del giorno invenduti', 'Panetteria',        'Glutine, Uova, Latte',        '12:30:00', '13:30:00');
SELECT setval(pg_get_serial_sequence('box', 'id'), (SELECT MAX(id) FROM box));

INSERT INTO cart (id, "userId", "storeId", status) VALUES
(1, 2, 1, 'active'),
(2, 2, 3, 'completed');
SELECT setval(pg_get_serial_sequence('cart', 'id'), (SELECT MAX(id) FROM cart));

INSERT INTO cart_item (id, "cartId", "boxId", quantity) VALUES
(1, 1, 1, 2),
(2, 2, 2, 1);
SELECT setval(pg_get_serial_sequence('cart_item', 'id'), (SELECT MAX(id) FROM cart_item));

INSERT INTO orders (id, "userId", "storeId", "totalPrice", state, "pickupWindow") VALUES
(1, 2, 3, 3.50, 'pickedUp', '12:30-13:30'),
(2, 2, 1, 9.98, 'pickedUp', '18:30-19:30');
SELECT setval(pg_get_serial_sequence('orders', 'id'), (SELECT MAX(id) FROM orders));

INSERT INTO order_item (id, "orderId", "boxId", quantity, "unitPrice") VALUES
(1, 1, 2, 1, 3.50),
(2, 2, 1, 2, 4.99);
SELECT setval(pg_get_serial_sequence('order_item', 'id'), (SELECT MAX(id) FROM order_item));

INSERT INTO review (id, "orderId", "userId", "storeId", rating, text) VALUES
(1, 1, 2, 3, 4.5, 'Pane buonissimo e ancora fresco, consigliatissimo!'),
(2, 2, 2, 1, 5.0, 'Frutta freschissima, tornerò sicuramente!');
SELECT setval(pg_get_serial_sequence('review', 'id'), (SELECT MAX(id) FROM review));

INSERT INTO notification (id, "userId", type, text, "isRead") VALUES
(1, 2, 'orderConfirmed',  'Il tuo ordine da Ortofrutta Bianchi è confermato.',              TRUE),
(2, 2, 'pickupReminder',  'Ricorda di ritirare il tuo box da Vivaio Rossi entro le 19:30.', FALSE);
SELECT setval(pg_get_serial_sequence('notification', 'id'), (SELECT MAX(id) FROM notification));

COMMIT;
