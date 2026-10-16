import { createApp } from "./app";
import { env } from "./config/env";

const app = createApp();

app.listen(env.port, () => {
  // eslint-disable-next-line no-console
  console.log(`API in ascolto su http://localhost:${env.port} (${env.nodeEnv})`);
});
