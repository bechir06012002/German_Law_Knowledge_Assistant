# Judges Said — Frontend checklist

Work top to bottom. Read [Architecture.md](Architecture.md) first.

**Pacing rule:** the frontend is a streaming chat shell with auth and citation display. It
must not run ahead of working backend APIs. Scaffold early (Phase 1–2), then stop and wait —
do not build citation UI until the backend actually returns citations, or you will build it
twice against a guessed shape.

| Frontend phase | Needs backend phase |
| -------------- | ------------------- |
| 1 Scaffold | — |
| 2 Auth | Backend Phase 2 |
| 3 Chat shell | Backend Phase 3 (stubbed stream) |
| 4 Trust UI | Backend Phase 6 (real citations) |
| 5 Bilingual UX | Backend Phase 5–6 |
| 6 Polish | all |

---

## Phase 1 — Scaffold

- [x] `pnpm create vite` — React + TypeScript (React 19, Vite 8, TypeScript 6)
- [x] Tailwind + shadcn/ui configured; confirm one shadcn component renders
      (Tailwind 4 via `@tailwindcss/vite`; shadcn `base` preset, `Button` renders)
- [x] React Router with routes: `/login`, `/`, `/chat/:threadId`
- [x] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`,
      `VITE_SUPABASE_ANON_KEY`; throw on startup if missing
- [x] Set `<html lang>` and page titles from the active language, defaulting to `de` —
      the product is bilingual DE/EN, see Phase 5 (`src/lib/language.ts`)
- [x] Verify: `pnpm build` typechecks and builds clean; `pnpm dev` serves `/`, `/login`,
      and `/src/main.tsx` with HTTP 200

Two version-specific gotchas, both silent if you copy older tutorials:

1. **TypeScript 6 deprecates `baseUrl`** — it errors outright. The `@/*` alias uses `paths`
   alone, which since TS 5 resolves relative to the tsconfig file itself.
2. **shadcn's `base` preset builds on base-ui, not Radix, so `Button` has no `asChild`.**
   Links that should look like buttons use the exported `buttonVariants()` instead.

---

## Phase 2 — Auth

- [x] `src/lib/supabase.ts` — browser client using the **anon key only**
      (the service-role key must never reach the frontend) — asserted in the test
- [x] `src/lib/http.ts` — fetch wrapper: base URL, automatic bearer token injection,
      timeout, typed `ApiError`; distinguish network/CORS failures from HTTP failures
- [x] `src/lib/api.ts` — product-level calls: list threads, create thread, load messages
- [x] Sign-in / sign-up pages, email only, German labels
- [x] `ProtectedRoute` — redirect unauthenticated users to `/login`
- [x] Session listener — redirect on token expiry rather than failing silently
      (`onAuthStateChange` in `src/lib/auth.tsx`)
- [x] Never pass tokens through component props; read them from the shared client
      (context carries `user` + `loading` only; `http.ts` reads the token per request)
- [x] Verify: 13/13 against the live Supabase project and a running backend — sign-up,
      sign-in, `/me` returns the matching user id, thread CRUD works, umlauts survive the
      round trip, garbage token → 401, stored token still resolves after a "reload"

Two behaviours of this Supabase project that shape the UI:

1. **Email confirmation is enabled**, so `signUp` returns a user but **no session** — a new
   account cannot use the app until the emailed link is clicked. The sign-up form says so
   explicitly rather than looking like it silently failed.
2. **The built-in mailer is rate-limited to a few sends per hour** (`over_email_send_rate_limit`,
   HTTP 429) and is documented by Supabase as test-only. Real signups need custom SMTP.
   `src/lib/authErrors.ts` maps this and the other common auth codes to German, because the
   raw text a user would otherwise see is developer-facing English.

---

## Phase 3 — Chat shell

- [x] `useChat` from the AI SDK pointed at `POST /chat/stream` with the Supabase bearer token
      in an async headers callback (the token can refresh mid-session)
- [x] Transport points at **FastAPI directly** — no frontend route handler, no proxy
- [x] Thread sidebar listing past conversations, newest first
- [x] Message list, input, send; initialize with stored messages then let the SDK own
      in-flight state
- [x] Streaming indicator while the assistant is running
- [x] Verify: 11/11 driving the real `DefaultChatTransport` against the running backend —
      chunk types `start, text-start, text-delta, text-end, finish`, 29 chunks, no error
      chunk; umlauts intact; stored history matches the streamed text exactly

The backend's SSE format is hand-written (`app/chat/streaming.py`), so the test drives the
actual SDK transport rather than asserting on raw bytes. Asserting the bytes would only prove
the backend matches *my reading* of the protocol; consuming them with the SDK proves the two
agree. Worth keeping that shape when citations are added as custom `data-` parts.

Enter sends, Shift+Enter adds a newline (Phase 6 asks for it; it costs three lines here).
Bundle is ~624 kB — fine for now, worth code-splitting in Phase 6.

---

## Phase 4 — Trust UI (the part that makes it usable)

Depends on backend Phase 6 returning real citations. This is the product's whole value —
a user must be able to verify every claim in one click.

- [x] Citation chips on assistant messages showing **court · Aktenzeichen · decision date**
      (`src/components/CitationChips.tsx`)
- [x] Source passage panel showing court, decision type, date, section label, the excerpt,
      and a link to `source_url` (`src/components/SourcePanel.tsx`)
- [x] Render the **section label**, not a page number — plus the Randnummer (`Rn. 22`) where
      the decision has one, which is the pinpoint a German citation actually uses
- [x] `norm_refs` display: the statutes a decision turns on, as chips (`§ 1 KSchG`)
- [x] Click a statute chip → shows the statute text. Live rather than hidden, because
      backend Phase 7 landed first — `GET /statutes/{book}/{section}` returns the § , and
      `text: null` (not a 404) when the corpus lacks it, so the UI says "nicht im Bestand"
      instead of showing an error for an ordinary gap. Measured: 5 of 6 chips resolve.
- [x] Verify: **10/10** against the live stack — every chip carries court, Aktenzeichen and a
      German-format date; every chip has a section label and never a page; court names are
      never localized; every citation carries the full passage the answer used.

**The gap this phase found, which no unit test would have caught.** Citations existed only in
the stream. Reloading a thread returned prose with **no evidence at all** — the rows were
sitting in `message_citations`, but `GET /threads/{id}/messages` never returned them, and the
frontend rebuilt history as text-only parts. For a product whose entire promise is "check
every claim in one click", an answer that loses its citations on refresh is worse than no
answer. Fixed on both sides: the endpoint joins the stored citations back, and
`toUIMessage` reconstructs the same `data-citations` part the stream sends, so a reloaded
conversation renders identically to a live one. Asserted: live 5 citations, after reload 5,
same chunk ids, same passage text.

Two smaller notes:

- **An English question shows the German search terms used.** If the query was not German,
  the answer carries *"Gesucht wurde auf Deutsch nach: Kündigungsfrist"* — an English speaker
  with thin results can see what was actually searched.
- **Testing this needs care about stale servers.** One run reported a false failure because
  uvicorn could not bind port 8000 (the previous instance still held it) and the test silently
  hit the *old* build. A second run hit the model's refusal path and the citation assertions
  passed vacuously against an empty list. Both are now visible in the test output rather than
  looking like passes.

## Phase 5 — Bilingual legal UX

The details that decide whether a non-lawyer trusts this. Users ask in German **or English**
and read answers in either — see [Architecture.md](Architecture.md) → "Bilingual behaviour".

**Language handling**

- [x] Answer-language toggle (`DE` / `EN`) on each assistant message, persisted on the thread
      (`src/components/AssistantMessage.tsx`, `LanguageToggle.tsx`). The toggle starts from
      the language the answer is actually in, which the backend **states** in the citations
      payload — see the umlaut trap below.
- [x] ~~Send `answer_language` with every chat request~~ → the opposite, and this was a real
      bug in use. The transport hardcoded `answer_language: 'de'`, so **every English question
      came back in German**. The frontend now sends nothing and the backend answers in the
      language the question was asked in; an explicit toggle still wins.
- [x] Switching the toggle re-renders the answer and does **not** change which cases are cited
      — **this needed a new backend endpoint**, see below
- [x] UI copy in both languages via a `t()` lookup and two dictionaries (`src/lib/i18n.ts`).
      No i18n framework: 40 kB to do what `dictionary[key]` does, for two languages.
- [x] `<html lang>` follows the selected language (`src/lib/uiLanguage.tsx`)
- [x] Show the German search terms actually used when the question was English —
      *"Gesucht wurde auf Deutsch nach: Kündigungsfrist"*

**The gap this phase closed.** Until now there was no way to re-render an existing answer:
toggling the language would have meant asking again, which re-runs retrieval and can surface
*different case law for the same situation*. Measured before the fix: the same question in
German and English shared only 2 of 3–4 decisions. `POST /messages/{id}/language` now
re-renders prose from the stored `message_citations` rows — retrieval is not involved, and the
same grounding validator runs against the same German source text.

Verified 7/7 against the live stack:

```text
GERMAN  cited: 1 Ca 751/23 | 1 Ca 751/23 | 4 Ca 2175/15 | 5 Ca 491/17 | 6 Ca 1273/21 | 8 Ca 1327/16 d
ENGLISH cited: 1 Ca 751/23 | 1 Ca 751/23 | 4 Ca 2175/15 | 5 Ca 491/17 | 6 Ca 1273/21 | 8 Ca 1327/16 d
```

**Evidence stays German — in both languages**

- [x] Citation chips render court, Aktenzeichen and date verbatim in German, never localized
      — asserted in English mode
- [x] Quoted passages display in the original German always, under an explicit
      "Originalwortlaut (Deutsch)" label, with `lang="de"` for screen readers
- [x] "Show unofficial translation" sits *beside* the German, labelled *"Inoffizielle
      Übersetzung — nicht verbindlich. Maßgeblich ist der deutsche Wortlaut."*, never
      replacing it
- [x] Dates always German style — the chips were already correct; the *model* wrote
      `2023-08-10` inside English prose, so `instructions.md` now requires `10.08.2023`
      everywhere a decision date is written, English text included
- [x] Aktenzeichen verbatim — asserted unchanged and unformatted after a language switch

**Three bugs found by using the app, not by the tests**

The Phase 5 suite passed while all three were live. Worth recording how each hid.

1. **The answer bubble rendered empty.** `AssistantMessage` did `useState(text)`, which
   copies a prop into state *once, on mount*. For a streaming answer that first render
   happens while the text is still `""`, so the bubble locked in the empty string and ignored
   every delta. The tests only exercised the *stored* path, never a live stream. Fixed with
   `const prose = override ?? text` — streamed text flows through, and state holds only a
   re-rendered translation.

2. **"Searched in German for: i was walking on the street…"** — English, under a German
   label. The glossary has no labour-law term for a dog bite, so `lexical_query` fell back to
   the raw English and built the tsquery
   `walking | the | street | and | bite | leg | …` against a **German** tsvector. That leg
   returned rows, so it looked healthy while contributing pure noise to the fusion. An
   untranslatable question now yields `""`, the leg is skipped, and RRF honestly degrades to
   semantic-only. Leg counts went from a fake `lexical: 40` to a truthful `lexical: 0`.

3. **Answers ignored the question's language** (above), and the *first fix for it was also
   wrong*: both my test and the frontend judged an answer's language by looking for umlauts.
   But an English answer legitimately contains `Arbeitsgericht`, `Kündigung`, `§ 622 BGB` and
   verbatim German quotes — that is the rule, not an exception — so every English answer was
   read as German. The backend now **states** `answerLanguage` in the citations payload and
   the UI reads it. Guessing at something the server already knows is how the same bug
   appears twice.

Verified afterwards, 6/6: German question → German prose, English question → English prose,
with `Arbeitsgericht Dortmund, 1 Ca 751/23` unchanged in both.

**Trust surface**

- [x] Umlauts and `ß` render correctly everywhere — asserted through the API round trip
- [x] A persistent, visible disclaimer in the active language, under the chat input and on
      the home page (`Keine Rechtsberatung` / `Not legal advice`)
- [x] Refusal states render as ordinary answers — the backend returns refusals as normal
      assistant messages with no citations, so they appear as prose, not errors
- [x] Empty states: no threads yet, no messages yet
- [x] Error states: `ApiError.kind` maps to localized copy, so "backend unreachable" and
      "session expired" read differently instead of both showing a raw exception

## Phase 6 — Polish & accessibility

- [x] Keyboard: Enter sends, Shift+Enter newlines, focus returns to the input after send
      (the focus return was missing — a keyboard user had to tab back every single turn)
- [x] Loading skeletons for the thread list and thread load (`src/components/Skeleton.tsx`),
      shaped like the content they replace so the layout does not jump
- [x] Long decision excerpts scroll inside their own container — the source panel is
      `overflow-x-hidden` with `break-words`, and the chat column is `min-w-0` so a long
      Aktenzeichen or URL cannot push the page body sideways
- [x] Mobile-usable layout — the sidebar was a fixed `w-64` column with **no way to reach the
      chat on a phone**. It is now off-canvas below `md` with a menu button, closing on
      navigation; padding tightens to `px-4` on small screens.
- [x] Screen-reader labels on citation chips and the source panel — each chip announces
      *"Fundstelle 1, Arbeitsgericht Dortmund, 1 Ca 751/23, 10.08.2023, Entscheidungsgründe,
      Randnummer 22"* rather than reading a row of truncated fragments
- [x] Light and dark themes both legible — **dark mode was unreachable**: shadcn ships a
      complete `.dark` token set but nothing ever applied the class, so the app was
      permanently light. `src/lib/theme.ts` honours the OS preference, remembers an explicit
      choice, and applies before the first paint so there is no white flash. Verified no
      hardcoded colours anywhere: every surface uses semantic tokens, and the only literal
      colours are two `bg-black/20` scrims, which are correct in both themes.
- [x] Verify: `tsc` clean, routes `/`, `/login`, `/chat` all serve 200, and the linter is down
      from 5 warnings to 1 — the last is in shadcn's own generated `button.tsx`, which their
      CLI regenerates, so it is left alone deliberately.

Two fixes worth their own note:

- **The provider/hook split.** `auth.tsx` and `uiLanguage.tsx` each exported a component *and*
  its hook, which breaks React Fast Refresh: editing the hook remounts the provider and drops
  the session mid-development. Contexts and hooks now live in `authContext.ts` and
  `uiLanguageContext.ts`.
- **Code-splitting.** The login screen was downloading the whole AI SDK — 624 kB before a user
  had signed in. The chat route is lazy now: 488 kB initial (144 kB gzipped) plus 150 kB
  loaded on demand.

## Deployment

- [ ] Railway static build for the Vite output
- [ ] `VITE_*` env vars set at **build** time, not runtime — Vite inlines them
- [ ] Confirm `VITE_API_BASE_URL` points at the deployed backend and that the backend's
      `ALLOWED_ORIGINS` includes this origin
- [ ] Verify: full flow on the deployed URL — sign in, ask, receive cited answer, click a
      citation

---

## Things not to build

- Outcome predictions, win-probability meters, or confidence scores on legal results
- Employer or person search, or any browse-by-party view
- Document drafting or letter generation
- A native mobile app
