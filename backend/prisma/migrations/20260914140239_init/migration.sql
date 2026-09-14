-- CreateEnum
CREATE TYPE "Ruolo" AS ENUM ('CLIENTE', 'VENDITORE', 'ADMIN');

-- CreateEnum
CREATE TYPE "StatoVerifica" AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

-- CreateEnum
CREATE TYPE "StatoCarrello" AS ENUM ('ATTIVO', 'COMPLETATO');

-- CreateEnum
CREATE TYPE "StatoOrdine" AS ENUM ('IN_ATTESA_PAGAMENTO', 'PAGATO', 'PRONTO_PER_RITIRO', 'RITIRATO', 'ANNULLATO', 'SCADUTO');

-- CreateTable
CREATE TABLE "utente" (
    "id" SERIAL NOT NULL,
    "role" "Ruolo" NOT NULL DEFAULT 'CLIENTE',
    "username" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "emailVerified" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "utente_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "email_verification_token" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "token" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "usedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "email_verification_token_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "password_reset_token" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "token" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "usedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "password_reset_token_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "refresh_token" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "token" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "refresh_token_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "negozio" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "nome" TEXT NOT NULL,
    "indirizzo" TEXT NOT NULL,
    "lat" DOUBLE PRECISION NOT NULL,
    "lng" DOUBLE PRECISION NOT NULL,
    "telefono" TEXT,
    "licenzaUrl" TEXT,
    "statoVerifica" "StatoVerifica" NOT NULL DEFAULT 'PENDING',
    "motivoRifiuto" TEXT,
    "orarioApertura" TEXT,
    "fasciaRitiro" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "negozio_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "categoria_box" (
    "id" SERIAL NOT NULL,
    "nome" TEXT NOT NULL,

    CONSTRAINT "categoria_box_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "box" (
    "id" SERIAL NOT NULL,
    "negozioId" INTEGER NOT NULL,
    "nome" TEXT NOT NULL,
    "descrizione" TEXT,
    "prezzo" DECIMAL(10,2) NOT NULL,
    "foto" TEXT,
    "categoriaId" INTEGER,
    "maxBox" INTEGER NOT NULL,
    "soldBoxes" INTEGER NOT NULL DEFAULT 0,
    "allergeni" TEXT,
    "fasciaRitiro" TEXT,
    "dataCreazione" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dataScadenza" TIMESTAMP(3),

    CONSTRAINT "box_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carrello" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "negozioId" INTEGER NOT NULL,
    "stato" "StatoCarrello" NOT NULL DEFAULT 'ATTIVO',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "carrello_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carrello_item" (
    "id" SERIAL NOT NULL,
    "carrelloId" INTEGER NOT NULL,
    "boxId" INTEGER NOT NULL,
    "quantita" INTEGER NOT NULL,
    "riservatoFino" TIMESTAMP(3),

    CONSTRAINT "carrello_item_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ordine" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "negozioId" INTEGER NOT NULL,
    "totalPrice" DECIMAL(10,2) NOT NULL,
    "stato" "StatoOrdine" NOT NULL DEFAULT 'IN_ATTESA_PAGAMENTO',
    "dataOrdine" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fasciaRitiro" TEXT,
    "stripePaymentIntentId" TEXT,

    CONSTRAINT "ordine_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ordine_item" (
    "id" SERIAL NOT NULL,
    "ordineId" INTEGER NOT NULL,
    "boxId" INTEGER NOT NULL,
    "quantita" INTEGER NOT NULL,
    "prezzoUnitario" DECIMAL(10,2) NOT NULL,

    CONSTRAINT "ordine_item_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recensione" (
    "id" SERIAL NOT NULL,
    "ordineId" INTEGER NOT NULL,
    "userId" INTEGER NOT NULL,
    "negozioId" INTEGER NOT NULL,
    "voto" INTEGER NOT NULL,
    "testo" TEXT,
    "segnalata" BOOLEAN NOT NULL DEFAULT false,
    "data" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "recensione_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notifica" (
    "id" SERIAL NOT NULL,
    "userId" INTEGER NOT NULL,
    "tipo" TEXT NOT NULL,
    "testo" TEXT NOT NULL,
    "letta" BOOLEAN NOT NULL DEFAULT false,
    "data" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notifica_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "utente_username_key" ON "utente"("username");

-- CreateIndex
CREATE UNIQUE INDEX "utente_email_key" ON "utente"("email");

-- CreateIndex
CREATE UNIQUE INDEX "email_verification_token_token_key" ON "email_verification_token"("token");

-- CreateIndex
CREATE INDEX "email_verification_token_userId_idx" ON "email_verification_token"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "password_reset_token_token_key" ON "password_reset_token"("token");

-- CreateIndex
CREATE INDEX "password_reset_token_userId_idx" ON "password_reset_token"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "refresh_token_token_key" ON "refresh_token"("token");

-- CreateIndex
CREATE INDEX "refresh_token_userId_idx" ON "refresh_token"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "negozio_userId_key" ON "negozio"("userId");

-- CreateIndex
CREATE INDEX "negozio_lat_lng_idx" ON "negozio"("lat", "lng");

-- CreateIndex
CREATE UNIQUE INDEX "categoria_box_nome_key" ON "categoria_box"("nome");

-- CreateIndex
CREATE INDEX "box_negozioId_idx" ON "box"("negozioId");

-- CreateIndex
CREATE INDEX "carrello_userId_idx" ON "carrello"("userId");

-- CreateIndex
CREATE INDEX "carrello_negozioId_idx" ON "carrello"("negozioId");

-- CreateIndex
CREATE UNIQUE INDEX "carrello_item_carrelloId_boxId_key" ON "carrello_item"("carrelloId", "boxId");

-- CreateIndex
CREATE INDEX "ordine_userId_idx" ON "ordine"("userId");

-- CreateIndex
CREATE INDEX "ordine_negozioId_idx" ON "ordine"("negozioId");

-- CreateIndex
CREATE UNIQUE INDEX "recensione_ordineId_key" ON "recensione"("ordineId");

-- CreateIndex
CREATE INDEX "recensione_negozioId_idx" ON "recensione"("negozioId");

-- CreateIndex
CREATE INDEX "notifica_userId_idx" ON "notifica"("userId");

-- AddForeignKey
ALTER TABLE "email_verification_token" ADD CONSTRAINT "email_verification_token_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "password_reset_token" ADD CONSTRAINT "password_reset_token_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "refresh_token" ADD CONSTRAINT "refresh_token_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "negozio" ADD CONSTRAINT "negozio_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "box" ADD CONSTRAINT "box_negozioId_fkey" FOREIGN KEY ("negozioId") REFERENCES "negozio"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "box" ADD CONSTRAINT "box_categoriaId_fkey" FOREIGN KEY ("categoriaId") REFERENCES "categoria_box"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carrello" ADD CONSTRAINT "carrello_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carrello" ADD CONSTRAINT "carrello_negozioId_fkey" FOREIGN KEY ("negozioId") REFERENCES "negozio"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carrello_item" ADD CONSTRAINT "carrello_item_carrelloId_fkey" FOREIGN KEY ("carrelloId") REFERENCES "carrello"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carrello_item" ADD CONSTRAINT "carrello_item_boxId_fkey" FOREIGN KEY ("boxId") REFERENCES "box"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ordine" ADD CONSTRAINT "ordine_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ordine" ADD CONSTRAINT "ordine_negozioId_fkey" FOREIGN KEY ("negozioId") REFERENCES "negozio"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ordine_item" ADD CONSTRAINT "ordine_item_ordineId_fkey" FOREIGN KEY ("ordineId") REFERENCES "ordine"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ordine_item" ADD CONSTRAINT "ordine_item_boxId_fkey" FOREIGN KEY ("boxId") REFERENCES "box"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recensione" ADD CONSTRAINT "recensione_ordineId_fkey" FOREIGN KEY ("ordineId") REFERENCES "ordine"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recensione" ADD CONSTRAINT "recensione_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recensione" ADD CONSTRAINT "recensione_negozioId_fkey" FOREIGN KEY ("negozioId") REFERENCES "negozio"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifica" ADD CONSTRAINT "notifica_userId_fkey" FOREIGN KEY ("userId") REFERENCES "utente"("id") ON DELETE CASCADE ON UPDATE CASCADE;
