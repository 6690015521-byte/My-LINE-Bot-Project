const express = require('express');
const line = require('@line/bot-sdk');
require('dotenv').config();

// ===== Config =====
const TRANSLATOR = (process.env.TRANSLATOR || 'GEMINI').toUpperCase();
const DEFAULT_CHINESE = (process.env.DEFAULT_CHINESE || 'zh-CN').trim();

const config = {
  channelAccessToken: process.env.LINE_CHANNEL_ACCESS_TOKEN,
  channelSecret: process.env.LINE_CHANNEL_SECRET,
};

if (!config.channelAccessToken || !config.channelSecret) {
  console.error('Missing LINE env vars.');
  process.exit(1);
}

const app = express();
const client = new line.Client(config);

// Health check
app.get('/', (req, res) => res.send('LINE Thai↔Chinese Translator: OK. Backend=' + TRANSLATOR));

// Webhook
app.post('/webhook', line.middleware(config), async (req, res) => {
  try {
    const results = await Promise.all(req.body.events.map(handleEvent));
    res.json(results);
  } catch (e) {
    console.error('webhook error', e);
    res.status(500).send('Error');
  }
});

// ===== Translator (Gemini) =====
let geminiModel = null;
async function ensureGemini() {
  if (geminiModel) return geminiModel;
  const { GoogleGenerativeAI } = require('@google/generative-ai');
  const key = process.env.GEMINI_API_KEY;
  const modelName = process.env.GEMINI_MODEL || 'gemini-1.5-flash';
  if (!key) throw new Error('GEMINI_API_KEY is missing');
  const genAI = new GoogleGenerativeAI(key);
  geminiModel = genAI.getGenerativeModel({
    model: modelName,
    systemInstruction:
      'You are a translation engine. Translate between Thai and Chinese (Simplified/Traditional). Return only the translated text.'
  });
  return geminiModel;
}

function detectByUnicode(text) {
  if (/[\u0E00-\u0E7F]/.test(text)) return 'th';
  if (/[\u3400-\u9FFF]/.test(text)) return 'zh';
  return null;
}

async function translateGemini(text, target, source) {
  const model = await ensureGemini();
  const langName = (code) => {
    if (!code) return 'auto';
    if (code === 'th') return 'Thai';
    if (code === 'zh' || code === 'zh-CN') return 'Simplified Chinese';
    if (code === 'zh-TW') return 'Traditional Chinese';
    return code;
  };
  const prompt = [
    `Translate from ${langName(source)} to ${langName(target)}.`,
    'Return ONLY the translated text.',
    'Text:',
    text,
    '-- END --',
  ].join('\n');
  const r = await model.generateContent(prompt);
  return (r?.response?.text() || '').trim();
}

// ===== Event handler =====
async function handleEvent(event) {
  if (event.type !== 'message' || event.message.type !== 'text') return null;
  const raw = (event.message.text || '').trim();

  // parse flags
  const useTraditional = /#tw/i.test(raw);
  let text = raw.replace(/#tw/ig, '').trim();
  const lower = text.toLowerCase();

  try {
    if (lower.startsWith('th->zh')) {
      text = text.slice(6).trim();
      const tgt = useTraditional ? 'zh-TW' : DEFAULT_CHINESE;
      const out = await translateGemini(text, tgt, 'th');
      return client.replyMessage(event.replyToken, { type: 'text', text: out });
    }
    if (lower.startsWith('zh->th')) {
      text = text.slice(6).trim();
      const out = await translateGemini(text, 'th', 'zh');
      return client.replyMessage(event.replyToken, { type: 'text', text: out });
    }

    // auto detect by unicode
    const src = detectByUnicode(text);
    if (src === 'th') {
      const tgt = useTraditional ? 'zh-TW' : DEFAULT_CHINESE;
      const out = await translateGemini(text, tgt, 'th');
      return client.replyMessage(event.replyToken, { type: 'text', text: out });
    } else if (src === 'zh') {
      const out = await translateGemini(text, 'th', 'zh');
      return client.replyMessage(event.replyToken, { type: 'text', text: out });
    } else {
      const tgt = useTraditional ? 'zh-TW' : DEFAULT_CHINESE;
      const out = await translateGemini(text, tgt);
      return client.replyMessage(event.replyToken, { type: 'text', text: out });
    }
  } catch (e) {
    console.error('translate failed', e);
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: 'ขออภัย ระบบแปลมีปัญหาชั่วคราว 🙏'
    });
  }
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Translator bot on', PORT, 'backend=', TRANSLATOR));