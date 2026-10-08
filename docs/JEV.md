# Jev (TypeSafe)

**Kjede:** Jev (Vercel AI Gateway) → **Mercury-2.5 + rules-veto** → rules. Logg: `src=jev+rules` | `src=mercury+rules` | `src=rules`.

Jev er ikke en chat-modell. Du sender **state** (kort JSON) + **typed questions**. Du får tall tilbake, aldri prosa.

| Primitive | Spørsmål | Svar |
|---|---|---|
| **Choice** | velg én av opptil 255 | vinner + fordeling + confidence |
| **Score** | plassér på 2–10 nivåer | score + fordeling |
| **Noul** | ja/nei | sannsynlighet 0–1 + confidence |

Passer når svaret er lukket og gjentas: rute, ranger, slå av/på, eskaler. Passer ikke når du trenger begrunnelse, kode eller flerhopps-resonnering.

## Minne-gaten

MiniLM finner like episoder. Jev (ellers Mercury, ellers rules) sier hva som *betyr noe*.

| Oppgave | Hvem |
|---|---|
| Hvilke episoder ligner spørsmålet? | MiniLM + sqlite |
| Av disse N, hvilke skal inn i Grok? | Jev Noul `keep` + Choice `act` |
| Trenger vi disk, eller holder minnet? | `use_memory` / `read_disk` / `both` |

Policy i kode: `keep < 0.6` droppes; `act=use_memory` fjerner tools i første runde. Jev skriver ikke systemprompt, velger ikke filer, kjører ikke bash. Stor skitten state senker nøyaktighet — filtrer først.

Adapter: `cockpit/backend/app/decide.py`. `gate_recall()` på uthenting, `classify_turn()` på slutt-engram. Uthenting og skriving bruker samme `decide()`.

## Hiroshima

Samme `decide()`, andre spørsmål. Sensorene eier strømmen (ss-familie, Falco-regler, AIDE). Jev porter et **ferdig-silt digest** til `noise` / `env_shift` / `candidate` / `alert_family`, pluss `ours`, `dual`, `playbook`. Mercury bare på candidate/alert. `signal` forklarer. Spekk: [HIROSHIMA.md](HIROSHIMA.md).

Jev klassifiserer ikke pakker. Trafikk er allerede merket. Jev sier hvilken slags *vindu* det er for operator.

`ai_enabled=false` og timer-scan: rules-port uten sky. Timeout ~4 s, ingen 429-retry.

## Hva vi ikke gjør

- Jev som «sikkerhetsagent» som later som SOC
- LangChain TypeSafeClassifier
- Bytte ut MiniLM
- Ny chat-provider bare for Jev
- Sende pcap, journal, cmdline eller full URL som state
