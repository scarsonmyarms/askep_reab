// Запускається з tests/test_extension_parity.py: node js_parity_runner.js <directory.json> <scenarios.json>
// Повертає (stdout, JSON) результати JS-логіки розширення для тих самих сценаріїв, що й Python.
const fs = require("fs");
const path = require("path");
const L = require(path.join(__dirname, "..", "extension", "logic.js"));

const dir = new L.Directory(JSON.parse(fs.readFileSync(process.argv[2], "utf8")));
const scenarios = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const flat = (rep) => ({
  main: rep.main, main_groups: rep.main_groups, exclusions: rep.exclusions, summary: rep.summary,
  companions: rep.companions.map(([n, ls]) => [n, ls]),
});
const out = scenarios.map((s) => {
  const main = dir.find(s.main);
  const sel = s.comps.map((c) => dir.find(c));
  const lists = main ? s.comps.map((_, i) => dir.companionCandidates(main, i, sel).length) : [];
  return {
    report: flat(L.validate(dir, s.period, s.main, s.comps, s.st)),
    lists,
    mains: dir.mainCandidates(s.period).length,
  };
});
process.stdout.write(JSON.stringify(out));
