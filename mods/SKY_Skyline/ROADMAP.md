# SKY_Skyline roadmap: "the city after" (D61)

This roadmap folds in the 23 ideas from the 2026-10-05 brainstorm (screenshots in the session; the French
text is quoted in the table). The direction is a dead city with a Pripyat melancholy:
- a rusting fair, a cinema, a mall and a hypermarket under harsh light;
- streets choked with abandoned cars, so the elevated roads and the one deadly bridge matter;
- hordes in the centre and an alarm that drags them across the city;
- small survival systems you can feel in the hands: searching bins, drinking at the bar, water from a hydrant.

Rules that do not change (CLAUDE.md):
- Security and performance are pass/fail gates.
- Every server handler validates the sender, the target, the distance and the rate.
- Every untested engine assumption is a named `P`-parameter in `assets/skyspec.py` (PENDING_VERIFICATION.md).
- Nothing is "done" before it ran in DayZ (TESTING.md).

## Phases

| Phase | Content | Depends on |
|---|---|---|
| **D61** (now) | venues, fair, landfill, stadium, parking lots, street props, viaducts, road tunnel, deadly bridge, car jams; gameplay: bin search, hydrants, alcohol, costumes, hordes, alarm | nothing new (vanilla APIs verified below) |
| **D62** creatures | dogs (guard + logout), rats (bites, disease, base damage, dog repels), horses | decision below: external mod (licence) or own animated creatures (needs an animator, skeleton + animation graph) |
| **D63** underground | sewers that flood in heavy rain, metro tunnels behind the hidden parking entrances | custom terrain (MOD_DEVELOPMENT_GUIDE 4.3 Level 2); objectSpawnersArr cannot cut the terrain |
| **D64** vehicles | drivable bus and garbage truck | a vehicle model with a working `CarScript` simulation (model.cfg, physics, damage zones); wrecks ship in D61 |

## The 23 ideas

| # | Idea (friend) | SKY feature | How | Phase | Status |
|---|---|---|---|---|---|
| 1 | "Une petite fête foraine (surtout grande roue, esthétique Chernobyl)" | **Funfair**: 26 m Ferris wheel with yellow gondolas (Pripyat palette, rust bleeding through), chain-swing carousel, bumper-car pavilion, ticket booths, entrance arch, bulb strings | `build_city.py` specials (`City_FerrisWheel`, `City_Carousel`, `City_BumperCars`, `City_FairBooth`, `City_FairGate`), placed as a `funfair` layout piece | D61 | built-unverified |
| 2 | "Des ponts et des tunnels ou c'est quasi impossible de passer en voiture tellement y a des voitures abandonnées" | **Car jams + bypasses**: streets jammed with vanilla wrecks (`Land_Wreck_*`, verified in vanilla types.xml), left with gaps players can walk through but vehicles cannot; **elevated viaducts** with ramps as the drivable routes; a **road tunnel** (cut-and-cover underpass, above terrain) | `sky_layout.py` `jams:`; kit pieces `Viaduct_*`, `Tunnel_*` (`sky_roads`) | D61 | built-unverified |
| 3 | "Les Z puissent créer des hordes en centre-ville" | **Horde director**: every siren tower downtown is a horde anchor. A player within 350 m wakes it: groups of 6 vanilla city infected spawn 60-140 m from the tower, at least 70 m from every player; 18 per anchor, 72 on the map, one group per anchor per 5 min; groups with no player within 550 m despawn, corpses go after 10 min | `SKY_CityLife` (4_World/SKY/SKY_CityLife.c), started by modded `MissionServer`; one 10 s timer | D61 | built-unverified (P15) |
| 4 | "Des hypermarchés avec une lumière blanche qui fait mal aux yeux" | **Hypermarket**: 48 x 36 m hall, tall racking, checkout lines, cold over-bright fluorescent tube rows. Night script light `SKY_HyperLight` (cold white, high intensity, flicker on damaged) | archetype `Hypermarket` (plan use `hyper`) | D61 | built-unverified |
| 5 | "Des chiens (ils protègent ton matos quand tu décos)…" | **Dogs**: guard dog that logs out with its owner and guards a stash; dog nearby = no rat attacks (#9) | see "Creatures" below | D62 | design |
| 6 | "Un cinéma !!!!! À la Kino der Toten" | **Cinema "KINO"**: art-deco facade, marquee with bulb frame, foyer with ticket and snack counters, raked auditorium with seat rows, curtains, screen, projection booth | archetype `Cinema` (plan use `cinema`) | D61 | built-unverified |
| 7 | "Un centre commercial à la Dead Island" | **Mall**: 3 levels round a glass-roofed atrium, galleries, static escalator banks (walkable ramps), fountain, palms, food court, shop units with shutters | archetype `Mall` (plan use `mall`) | D61 | built-unverified |
| 8 | "Des rats qui dégradent les installations et mordent les joueurs (dégâts + maladies)" | **Rats**: bites (damage + `SALMONELLA` agent), slow damage to base-building parts near nests | see "Creatures" below | D62 | design (rules written) |
| 9 | "Si un joueur a un chien à proximité, aucune attaque de rat" | rat attacks skip players with a dog within 15 m | same | D62 | design |
| 10 | "Des bars avec de l'alcool (soigne des blessures ou rend alcoolisé + vomir selon la dose)" | **Bar** (counter, bottle walls, stools, booths) whose stock is searchable. **Vodka / beer** (`SKY_Bottle_Vodka` / `SKY_Bottle_Beer`: vanilla glass bottle, vanilla liquids `LIQUID_VODKA` / `LIQUID_BEER`, constants.c:546-547), CE in towns. Dose model (ml of ethanol, decays 3 ml/min):<br>- tipsy (8 ml, about a shot): slow health + shock regen;<br>- drunk (30 ml): shock regen, blur;<br>- wasted (60 ml): strong blur, vomiting every 90 s (vanilla `SYMPTOM_VOMIT`) | archetype `Bar` (`skySearch = "alcohol"`); items in `sky_items`; modded `PlayerBase.Consume` / `OnScheduledTick` (SKY_PlayerLife.c), one synced int + client PPE requester | D61 | built-unverified (P16) |
| 11 | "Des chevaux à chevaucher" | **Horses** | see "Creatures" below | D62 | design |
| 12 | "Des églises avec des cadavres pendus" | **Church, hanged variant**: shrouded hanged bodies from the roof trusses (wrapped, not gory), toppled pews, candles, rope coils, crows-and-dust mood | archetype `ChurchHanged` (variant of `Church`, decor `hanged`) | D61 | built-unverified |
| 13 | "Une décharge où les joueurs peuvent trouver un peu de tout" | **Landfill**: 40 x 40 m: trash mounds, crushed appliance heaps, compactor shed, fence, gate; heaps are searchable (#16); wide CE loot (all categories, low value) | special `City_Landfill` + search points | D61 | built-unverified |
| 14 | "Une crèche, ça sera morbidement génial" | **Kindergarten**: 2 storeys, low tables and tiny chairs, cots in a nap room, toy shelves, faded mural, coat hooks; playground with rusty swings, slide, sandbox and a merry-go-round. Morbid by absence: no bodies | archetype `Kindergarten` (plan use `creche`), forecourt playground | D61 | built-unverified |
| 15 | "Des bus, ou des camions poubelles" | bus wrecks (vanilla `Land_Wreck_Ikarus_DE`) in the jams; **garbage truck** wreck model (ours); drivable versions in D64 | jams + `City_GarbageTruck` | D61 / D64 | wrecks built-unverified |
| 16 | "Les poubelles / qu'ils puissent fouiller les poubelles" | **Bins, dumpsters, garbage trucks and landfill heaps are searchable**: 6 s full-body search at a `search` memory point; each spot gives loot once per 30 min (server clock); the loot table is server-side; distance and per-player rate are re-checked on the server; 1 in 8 bare-handed searches cuts the hand (bleeding) | player action `ActionSKY_Search` + `SKY_SearchService`; targets carry `skySearch = "<table>"` in config (skyspec.SEARCH_TABLE) | D61 | built-unverified (P17) |
| 17 | "Certaines bouches incendie puissent donner de l'eau" | **Hydrants**: `Hydrant_Wet` behaves like a vanilla well (drink, fill, wash; well.c), `Hydrant_Dry` is decoration; layouts mix about 1 in 3 wet | `Land_SKY_Hydrant_Wet` extends vanilla `Well` | D61 | built-unverified |
| 18 | "Le niveau dans les égouts augmente s'il pleut beaucoup" | **Sewers flood**: water plane height driven by `Weather.GetRain()`, damage / wetness below it | needs sewers under the terrain | D63 | design |
| 19 | "Trouver des costumes / robe de soirée, pour les trollers" | **Costume racks**: the mall clothes rails and two costume trunks on the cinema stage are searchable and hand out vanilla `ManSuit_*`, `WomanSuit_*`, `MiniDress_*`, `NurseDress_*`, `Skirt_*`, `DressShoes_*`, `MimeMask_*` (no vanilla types overrides needed) | search table `costume` (archetypes `Mall`, `Cinema`) | D61 | built-unverified (P17) |
| 20 | "De temps en temps une énorme alarme se déclenche et ramène tous les Z à des kilomètres" | **City alarm**: siren towers; every 45-90 min (random, server) one tower with a player within 1.5 km wails for a minute. Players within 2.5 km hear it (procedural siren, `sky_sounds`); an AI noise target at the tower is refreshed every 10 s (vanilla alarm clock noise x 25) and 3 extra groups spawn 180-320 m out and walk in | `SKY_CityLife` + server -> client RPC `SKY_Life.RPC_SIREN`; `assets/sounds/gen_siren.py` | D61 | built-unverified (P14, P20) |
| 21 | "Un terrain de foot avec vestiaire et tout" | **Football ground**: pitch with worn lines, goals with torn nets, a covered stand, 4 floodlight masts, and a clubhouse with changing rooms, showers, benches and lockers | special `City_FootballPitch` + archetype `Clubhouse` (plan use `changing`) | D61 | built-unverified |
| 22 | "Plein de parkings; certains nuls, d'autres cachent des entrées dissimulées pour le métro" | **Surface car parks** (lines, lamp posts, wreck clusters, ticket booth); variant `ParkingLot_Metro` with a hidden service hatch (sealed in D61, opens onto the metro in D63) | specials `City_ParkingLot_A/B`, `City_ParkingLot_Metro` | D61 / D63 | built-unverified |
| 23 | "Un pont où le prendre te donne 95 % de chance d'un fight et 80 % de clamser" | **"The Bridge"**: a 96 m girder bridge as the only crossing between halves of the city. A barricaded checkpoint with a pile-up in the middle, sniper nests in the pylons, and the best loot on the map in the wrecked convoy at the centre (military loot points, weapons). Long sightlines, no cover off the deck | kit `Bridge_Long_*` (`sky_roads`), layout `bridges:` | D61 | built-unverified |

## Creatures (D62) - decision needed

Animated creatures need a skeleton, animations and an animation graph made in Workbench. The procedural
pipeline cannot produce that at the quality bar. Two routes:

1. **Existing mods (fastest)**, all by Hunterz:
   - [DayZ-Dog](https://steamcommunity.com/sharedfiles/filedetails/?id=2471347750): follow / patrol / stay; it logs out with its owner, exactly idea 5. Requires CF, no repacks, and **server use is restricted**: the page lists authorised server packs, so permission is needed.
   - [DayZ-Rat](https://steamcommunity.com/sharedfiles/filedetails/?id=2950280649): roaming rats you can kill and skin. They do **not** bite or damage bases.
   - [DayZ Horse](https://steamcommunity.com/sharedfiles/filedetails/?id=3295021220): rideable, needs CF + Survivor Animations, and the page is **removed from Steam**.

   SKY would add only the glue:
   - a rat "attack" layer: server bites near a rat entity, a disease agent, and base damage near nests;
   - the dog-repels-rats rule.

   The glue goes behind a `#ifdef` define, so SKY runs without them.
2. **Own creatures**: commission or build a rat and a dog in Workbench and drive them with SKY scripts.
   This costs more, but the licensing is clean and they match the mod's look.

**Recommendation**: rats and dogs through route 1 as optional server mods, if the server owner gets
DayZ-Dog's authorisation. Horses are on hold (the mod was pulled). The rat-bite / base-damage /
dog-protection rules are specified here so either route plugs in:

- **Bite**: a rat within 1.5 m, the player not in a vehicle and no dog within 15 m. Server rolls every 4 s per rat with 25 % chance: 3-6 health, a light bleed in 1 of 5 bites, and `SALMONELLA` 1 bite in 6.
- **Bases**: every 10 min each nest within 25 m of a base part (fence, watchtower, tent) removes 0.5 % health; a dog within 30 m or a burning fireplace within 10 m blocks it.

## Underground (D63)

objectSpawnersArr places objects on top of the terrain. A stair or hatch cannot lead below the terrain
surface without a terrain hole, so SKY_Skyline keeps the metro sealed (D58) and builds tunnels above
ground (cut-and-cover). On a custom terrain (Level 2), the sewers and metro become one network:
- service hatches in the `ParkingLot_Metro` pieces;
- flood level = `clamp(rain - 0.6, 0, 0.4) / 0.4 * 1.2 m`, raised over 10 min and drained over 30 min;
- underground darkness through vanilla `cfgundergroundtriggers.json`, a format that exists on Livonia.

## New pending parameters (PENDING_VERIFICATION.md)

P14 alarm noise reach, P15 horde caps, P16 drunk thresholds, P17 search cooldown and loot tables,
P18 wet hydrant = vanilla well behaviour on a spawned object, P19 jam density (are vehicles really blocked?),
P20 siren sound config (range, loudness). All are in the PENDING_VERIFICATION.md table with their fix.

## Status (end of D61)

Everything in the D61 row is built and passes the offline gates (`reviews/d61_gates.md`); nothing ran in
DayZ yet (TESTING §26). Next: the joint test session (TEST_SESSION.md + §26), then D62 needs the creature
decision above, D63 a custom terrain, D64 a vehicle simulation.
