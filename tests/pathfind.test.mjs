// node tests/pathfind.test.mjs — tests the exact module the browser runs.
import { buildAdj, findPath, profAt } from "../public/app.js";
import assert from "node:assert";

// people: 0 A, 1 B, 2 Manning, 3 Clean intermediate, 4 Prof (Stanford 2010-),
// 5 OldProf (Stanford prof only until 2005), 6 Isolated
const mk = (papers) =>
  buildAdj({
    people: [
      { name: "A" },
      { name: "B" },
      { name: "Manning", m: 1 },
      { name: "Clean" },
      { name: "Prof", prof: [2010, null] },
      { name: "OldProf", prof: [1990, 2005] },
      { name: "Isolated" },
    ],
    papers,
  });

let t = 0;
const ok = (name, cond) => {
  t++;
  assert(cond, name);
  console.log(`ok ${t} - ${name}`);
};

// direct co-authorship
{
  const G = mk([{ t: "p1", y: 2020, p: [0, 1] }]);
  const r = findPath(G, 0, 1);
  ok("direct hit, 1 degree", r.found && r.papers.length === 1);
}

// Manning may not be an intermediate...
{
  const G = mk([
    { t: "a-m", y: 2020, p: [0, 2] },
    { t: "m-b", y: 2020, p: [2, 1] },
  ]);
  ok("manning blocked as link", !findPath(G, 0, 1).found);
  ok("manning allowed when asked", findPath(G, 0, 1, { allowManning: true }).found);
}

// ...but is a legal endpoint
{
  const G = mk([
    { t: "a-c", y: 2020, p: [0, 3] },
    { t: "c-m", y: 2020, p: [3, 2] },
  ]);
  const r = findPath(G, 0, 2);
  ok("manning as endpoint ok", r.found && r.people.at(-1) === 2);
}

// detour beats forbidden shortcut
{
  const G = mk([
    { t: "a-m", y: 2020, p: [0, 2] },
    { t: "m-b", y: 2020, p: [2, 1] },
    { t: "a-c", y: 2020, p: [0, 3] },
    { t: "c-b", y: 2020, p: [3, 1] },
  ]);
  const r = findPath(G, 0, 1);
  ok("routes around manning", r.found && !r.people.includes(2));
}

// strict mode: Prof (Stanford since 2010) cannot link via 2015 papers
{
  const G = mk([
    { t: "a-p", y: 2015, p: [0, 4] },
    { t: "p-b", y: 2015, p: [4, 1] },
  ]);
  ok("loose mode allows prof", findPath(G, 0, 1).found);
  ok("strict blocks prof-at-time", !findPath(G, 0, 1, { strict: true }).found);
}

// strict mode: same person fine via papers BEFORE their professorship
{
  const G = mk([
    { t: "a-p old", y: 2005, p: [0, 4] },
    { t: "p-b old", y: 2006, p: [4, 1] },
  ]);
  ok("strict allows pre-tenure papers", findPath(G, 0, 1, { strict: true }).found);
}

// strict: blocked if EITHER adjacent paper is in tenure (one old, one new)
{
  const G = mk([
    { t: "a-p old", y: 2005, p: [0, 4] },
    { t: "p-b new", y: 2015, p: [4, 1] },
  ]);
  ok("strict blocks mixed-era prof", !findPath(G, 0, 1, { strict: true }).found);
}

// strict: ex-prof fine after leaving
{
  const G = mk([
    { t: "a-o", y: 2012, p: [0, 5] },
    { t: "o-b", y: 2013, p: [5, 1] },
  ]);
  ok("strict allows ex-prof", findPath(G, 0, 1, { strict: true }).found);
}

// strict: unknown year treated conservatively for profs
{
  const G = mk([
    { t: "a-p", y: null, p: [0, 4] },
    { t: "p-b", y: null, p: [4, 1] },
  ]);
  ok("strict blocks unknown-year prof", !findPath(G, 0, 1, { strict: true }).found);
  ok("loose allows unknown-year prof", findPath(G, 0, 1).found);
}

// endpoints exempt from strict rule
{
  const G = mk([{ t: "p-b", y: 2015, p: [4, 1] }]);
  ok("prof endpoint exempt", findPath(G, 4, 1, { strict: true }).found);
}

// multi-hop + path shape
{
  const G = mk([
    { t: "a-c", y: 2001, p: [0, 3] },
    { t: "c-o", y: 2002, p: [3, 5] },
    { t: "o-b", y: 2003, p: [5, 1] },
  ]);
  const r = findPath(G, 0, 1);
  ok(
    "3 degrees, alternating shape",
    r.found && r.papers.length === 3 && r.people.length === 4 &&
      r.people[0] === 0 && r.people.at(-1) === 1
  );
}

// no path at all
{
  const G = mk([{ t: "a-c", y: 2001, p: [0, 3] }]);
  ok("disconnected pair fails", !findPath(G, 0, 6).found);
}

// same person
ok("reflexive = 0 degrees", findPath(mk([]), 0, 0).papers.length === 0);

// profAt sanity
ok("profAt in range", profAt({ prof: [2010, null] }, 2015));
ok("profAt before", !profAt({ prof: [2010, null] }, 2009));
ok("profAt after end", !profAt({ prof: [1990, 2005] }, 2006));
ok("profAt unknown year strict", profAt({ prof: [2010, null] }, null));
ok("profAt non-prof", !profAt({}, 2015));

console.log(`\n${t} tests passed`);
