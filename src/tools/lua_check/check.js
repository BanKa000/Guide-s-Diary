// Строгая проверка синтаксиса Lua 5.1 для скриптов мода (вызывает diary_build.py).
// node check.js <папка со .script> [<папка> ...]  - файлы в cp1251; вывод: "файл: [строка:столбец] ошибка"
const fs = require('fs');
const path = require('path');
const luaparse = require('./luaparse.js');

const dec = new TextDecoder('windows-1251');
let bad = 0;
for (const dir of process.argv.slice(2)) {
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.script'))) {
    const src = dec.decode(fs.readFileSync(path.join(dir, f)));
    try {
      luaparse.parse(src, { luaVersion: '5.1', comments: false });
    } catch (e) {
      bad++;
      console.log(f + ': ' + e.message);
    }
  }
}
process.exit(bad > 0 ? 1 : 0);
