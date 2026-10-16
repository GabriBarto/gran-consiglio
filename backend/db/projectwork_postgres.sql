CREATE TYPE "user_role" AS ENUM('client', 'seller', 'admin');
CREATE TYPE "verification_status" AS ENUM('pending', 'approved', 'rejected');
CREATE TYPE "cart_status" AS ENUM('active', 'completed');
CREATE TYPE "order_state" AS ENUM('pendingPayment', 'paid', 'readyForPickup', 'pickedUp', 'cancelled', 'expired');
CREATE TYPE "push_platform" AS ENUM('ios', 'android');

CREATE TABLE "box" (
	"id" serial PRIMARY KEY,
	"storeId" integer NOT NULL,
	"name" varchar(50) NOT NULL,
	"price" double precision NOT NULL,
	"creationDate" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	"expireDate" timestamp,
	"maxBoxes" integer NOT NULL,
	"soldBoxes" integer DEFAULT 0 NOT NULL,
	"description" varchar(250) NOT NULL,
	"category" varchar(100) NOT NULL,
	"allergens" varchar(250) NOT NULL,
	"pickupWindowStart" time NOT NULL,
	"pickupWindowEnd" time NOT NULL
);
CREATE TABLE "cart" (
	"id" serial PRIMARY KEY,
	"userId" integer NOT NULL,
	"storeId" integer NOT NULL,
	"status" cart_status DEFAULT 'active' NOT NULL
);
CREATE TABLE "cart_item" (
	"id" serial PRIMARY KEY,
	"cartId" integer NOT NULL,
	"boxId" integer NOT NULL,
	"quantity" integer NOT NULL
);
CREATE TABLE "email_verification" (
	"userId" integer PRIMARY KEY,
	"otp" varchar(6) NOT NULL,
	"expiresAt" timestamp NOT NULL
);
CREATE TABLE "notification" (
	"id" serial PRIMARY KEY,
	"userId" integer NOT NULL,
	"type" varchar(30) NOT NULL,
	"text" varchar(100) NOT NULL,
	"isRead" boolean DEFAULT false NOT NULL,
	"date" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE TABLE "order_item" (
	"id" serial PRIMARY KEY,
	"orderId" integer NOT NULL,
	"boxId" integer NOT NULL,
	"quantity" integer NOT NULL,
	"unitPrice" double precision NOT NULL
);
CREATE TABLE "orders" (
	"id" serial PRIMARY KEY,
	"userId" integer NOT NULL,
	"storeId" integer NOT NULL,
	"totalPrice" double precision NOT NULL,
	"orderDate" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	"state" order_state DEFAULT 'pendingPayment' NOT NULL,
	"pickupWindow" varchar(20) NOT NULL
);
CREATE TABLE "password_reset" (
	"userId" integer PRIMARY KEY,
	"jti" varchar(64) NOT NULL,
	"expiresAt" timestamp NOT NULL
);
CREATE TABLE "push_token" (
	"id" serial PRIMARY KEY,
	"userId" integer NOT NULL,
	"token" varchar(255) NOT NULL,
	"platform" push_platform NOT NULL,
	"createdAt" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE TABLE "refresh_token" (
	"id" serial PRIMARY KEY,
	"jti" varchar(64) NOT NULL CONSTRAINT "refresh_token_jti_key" UNIQUE,
	"userId" integer NOT NULL,
	"revoked" boolean DEFAULT false NOT NULL,
	"expiresAt" timestamp NOT NULL,
	"createdAt" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE TABLE "review" (
	"id" serial PRIMARY KEY,
	"orderId" integer NOT NULL,
	"userId" integer NOT NULL,
	"storeId" integer NOT NULL,
	"rating" double precision NOT NULL,
	"text" varchar(500) NOT NULL,
	"date" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE TABLE "store" (
	"id" serial PRIMARY KEY,
	"userId" integer NOT NULL,
	"name" varchar(50) NOT NULL,
	"address" varchar(100) NOT NULL,
	"latitude" numeric(10, 8) NOT NULL,
	"longitude" numeric(11, 8) NOT NULL,
	"phone" varchar(20) NOT NULL,
	"licenseUrl" varchar(255) NOT NULL,
	"verificationStatus" verification_status DEFAULT 'pending' NOT NULL,
	"openingTime" time NOT NULL,
	"pickupWindowStart" time NOT NULL,
	"pickupWindowEnd" time NOT NULL
);
CREATE TABLE "user" (
	"id" serial PRIMARY KEY,
	"role" user_role NOT NULL,
	"username" varchar(50) NOT NULL CONSTRAINT "user_username_key" UNIQUE,
	"email" varchar(100) NOT NULL CONSTRAINT "user_email_key" UNIQUE,
	"password" varchar(255) NOT NULL,
	"email_verified" boolean DEFAULT false NOT NULL,
	"created_at" timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX "box_pkey" ON "box" ("id");
CREATE INDEX "fk_box_store" ON "box" ("storeId");
CREATE UNIQUE INDEX "cart_pkey" ON "cart" ("id");
CREATE INDEX "fk_cart_store" ON "cart" ("storeId");
CREATE INDEX "fk_cart_user" ON "cart" ("userId");
CREATE UNIQUE INDEX "cart_item_pkey" ON "cart_item" ("id");
CREATE INDEX "fk_cartitem_box" ON "cart_item" ("boxId");
CREATE INDEX "fk_cartitem_cart" ON "cart_item" ("cartId");
CREATE UNIQUE INDEX "email_verification_pkey" ON "email_verification" ("userId");
CREATE INDEX "fk_notification_user" ON "notification" ("userId");
CREATE UNIQUE INDEX "notification_pkey" ON "notification" ("id");
CREATE INDEX "fk_orderitem_box" ON "order_item" ("boxId");
CREATE INDEX "fk_orderitem_order" ON "order_item" ("orderId");
CREATE UNIQUE INDEX "order_item_pkey" ON "order_item" ("id");
CREATE INDEX "fk_order_store" ON "orders" ("storeId");
CREATE INDEX "fk_order_user" ON "orders" ("userId");
CREATE UNIQUE INDEX "orders_pkey" ON "orders" ("id");
CREATE UNIQUE INDEX "password_reset_pkey" ON "password_reset" ("userId");
CREATE UNIQUE INDEX "push_token_pkey" ON "push_token" ("id");
CREATE UNIQUE INDEX "push_token_token_key" ON "push_token" ("token");
CREATE INDEX "fk_pushtoken_user" ON "push_token" ("userId");
CREATE INDEX "fk_refreshtoken_user" ON "refresh_token" ("userId");
CREATE UNIQUE INDEX "refresh_token_jti_key" ON "refresh_token" ("jti");
CREATE UNIQUE INDEX "refresh_token_pkey" ON "refresh_token" ("id");
CREATE INDEX "fk_review_order" ON "review" ("orderId");
CREATE INDEX "fk_review_store" ON "review" ("storeId");
CREATE INDEX "fk_review_user" ON "review" ("userId");
CREATE UNIQUE INDEX "review_pkey" ON "review" ("id");
CREATE INDEX "fk_store_user" ON "store" ("userId");
CREATE UNIQUE INDEX "store_pkey" ON "store" ("id");
CREATE UNIQUE INDEX "user_email_key" ON "user" ("email");
CREATE UNIQUE INDEX "user_pkey" ON "user" ("id");
CREATE UNIQUE INDEX "user_username_key" ON "user" ("username");

ALTER TABLE "box" ADD CONSTRAINT "box_storeId_fkey" FOREIGN KEY ("storeId") REFERENCES "store"("id") ON DELETE CASCADE;
ALTER TABLE "cart" ADD CONSTRAINT "cart_storeId_fkey" FOREIGN KEY ("storeId") REFERENCES "store"("id") ON DELETE CASCADE;
ALTER TABLE "cart" ADD CONSTRAINT "cart_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "cart_item" ADD CONSTRAINT "cart_item_boxId_fkey" FOREIGN KEY ("boxId") REFERENCES "box"("id") ON DELETE CASCADE;
ALTER TABLE "cart_item" ADD CONSTRAINT "cart_item_cartId_fkey" FOREIGN KEY ("cartId") REFERENCES "cart"("id") ON DELETE CASCADE;
ALTER TABLE "email_verification" ADD CONSTRAINT "email_verification_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "notification" ADD CONSTRAINT "notification_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "order_item" ADD CONSTRAINT "order_item_boxId_fkey" FOREIGN KEY ("boxId") REFERENCES "box"("id");
ALTER TABLE "order_item" ADD CONSTRAINT "order_item_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "orders"("id") ON DELETE CASCADE;
ALTER TABLE "orders" ADD CONSTRAINT "orders_storeId_fkey" FOREIGN KEY ("storeId") REFERENCES "store"("id");
ALTER TABLE "orders" ADD CONSTRAINT "orders_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id");
ALTER TABLE "password_reset" ADD CONSTRAINT "password_reset_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "push_token" ADD CONSTRAINT "push_token_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "refresh_token" ADD CONSTRAINT "refresh_token_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "review" ADD CONSTRAINT "review_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "orders"("id") ON DELETE CASCADE;
ALTER TABLE "review" ADD CONSTRAINT "review_storeId_fkey" FOREIGN KEY ("storeId") REFERENCES "store"("id") ON DELETE CASCADE;
ALTER TABLE "review" ADD CONSTRAINT "review_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
ALTER TABLE "store" ADD CONSTRAINT "store_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE;
