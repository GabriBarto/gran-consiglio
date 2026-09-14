import { PrismaClient } from "@prisma/client";
import { hashPassword } from "../src/utils/password";

const prisma = new PrismaClient();

const CATEGORIE_BOX = ["Interno", "Esterno", "Sempreverde", "Fiorita", "Bassa altezza", "Alta altezza"];

async function main() {
  for (const nome of CATEGORIE_BOX) {
    await prisma.categoriaBox.upsert({ where: { nome }, create: { nome }, update: {} });
  }
  console.log(`Categorie box seedate: ${CATEGORIE_BOX.join(", ")}`);

  // Admin di sviluppo — cambia subito email/password prima di andare in produzione.
  const adminEmail = "admin@example.com";
  const existingAdmin = await prisma.utente.findUnique({ where: { email: adminEmail } });
  if (!existingAdmin) {
    await prisma.utente.create({
      data: {
        username: "admin",
        email: adminEmail,
        passwordHash: await hashPassword("ChangeMe123"),
        role: "ADMIN",
        emailVerified: true,
      },
    });
    console.log(`Admin di sviluppo creato: ${adminEmail} / ChangeMe123 (cambia la password!)`);
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
