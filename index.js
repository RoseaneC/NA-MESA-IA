const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const axios = require('axios');

const PORT = process.env.PORT || 3000;
const URL_PYTHON = process.env.URL_PYTHON || 'http://127.0.0.1:8000/webhook';

const app = express();
app.use(express.json());

let clientInstance;

wppconnect
  .create({ session: 'vexia-session' })
  .then((client) => {
    clientInstance = client;
    console.log(`WPPConnect iniciado. Encaminhando para ${URL_PYTHON}`);

    client.onMessage(async (message) => {
      if (!message) return;
      if (message.from === 'status@broadcast') return;
      if (message.isGroupMsg) return;
      if (message.fromMe) return;

      const body = (message.body || '').trim();
      if (!body) return;

      console.log(`👂 Ouvi de ${message.from}: ${body}`);

      try {
        await axios.post(
          URL_PYTHON,
          { numero: message.from, mensagem: body },
          { timeout: 5000 }
        );
      } catch (err) {
        console.error('Falha ao repassar para Python:', err.message);
      }
    });
  })
  .catch((error) => console.error('Erro ao iniciar WPPConnect:', error));

app.post('/send', async (req, res) => {
  const numero = (req.body && req.body.numero) || '';
  const mensagem = (req.body && req.body.mensagem) || '';

  if (!numero || !mensagem) {
    return res.status(400).json({ status: 'erro', detail: 'numero e mensagem são obrigatórios' });
  }

  if (!clientInstance) {
    return res.status(503).json({ status: 'erro', detail: 'cliente não está pronto' });
  }

  const digits = (numero || '').replace(/\D/g, '');
  const to = numero.includes('@') ? numero : `${digits}@c.us`;

  try {
    await clientInstance.sendText(to, mensagem);
    return res.json({ status: 'ok' });
  } catch (err) {
    console.error('Erro ao enviar mensagem para WhatsApp:', err.message);
    return res.status(500).json({ status: 'erro', detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Bridge Node ouvindo em http://0.0.0.0:${PORT}`);
});

