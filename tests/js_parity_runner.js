// Запускається з tests/test_extension_parity.py: node js_parity_runner.js <directory.json> <scenarios.json>
// Повертає (stdout, JSON) результати JS-логіки розширення для тих самих сценаріїв, що й Python.
const fs = require("fs");
const path = require("path");
const L = require(path.join(__dirname, "..", "extension", "logic.js"));

const dir = new L.Directory(JSON.parse(fs.readFileSync(process.argv[2], "utf8")));
const scenarios = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const flat = (rep) => ({
  main: rep.main, main_groups: rep.main_groups, exclusions: rep.exclusions, summary: rep.summary, services: rep.services,
  companions: rep.companions.map(([n, ls]) => [n, ls]),
});
const out = scenarios.map((s) => {
  if (s.values) {   // план полів за ролями
    const main = dir.find(s.main);
    const slots = L.planSlots(dir, main, s.values);
    return {
      plan: slots.map((x, i) => [x.key, x.role, x.label, x.value, L.slotCandidates(dir, main, slots, i).length, L.slotFits(x)]),
      report: flat(L.validate(dir, s.period, s.main, slots.map((x) => x.value), s.st, { setting: s.setting, sr: s.sr })),
    };
  }
  const main = dir.find(s.main);
  const sel = s.comps.map((c) => dir.find(c));
  const lists = main ? s.comps.map((_, i) => dir.companionCandidates(main, i, sel).length) : [];
  return {
    report: flat(L.validate(dir, s.period, s.main, s.comps, s.st, { setting: s.setting, sr: s.sr })),
    lists,
    mains: dir.mainCandidates(s.period).length,
  };
});
process.stdout.write(JSON.stringify(out));
