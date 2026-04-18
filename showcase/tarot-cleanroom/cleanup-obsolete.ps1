const fs = require('fs');
const files = [
  'content/tarot/minor-arcana-pentacles.json',
  'content/tarot/minor-arcana-swords.json',
  'content/tarot/minor-arcana-wands-cups.json',
];
for (const f of files) {
  try {
    fs.unlinkSync(f);
    console.log('deleted:', f);
  } catch (e) {
    console.log('skip:', f, '—', e.code);
  }
}
