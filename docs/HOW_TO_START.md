# How to start SafeTrail and run the CSED demo

## Start everything (one command)

Double-click **Start SafeTrail.command** on the Desktop, or run this:

```bash
bash ~/safetrail/scripts/run_phones.sh
```

It rebuilds the screens if needed, starts the app and a public https link together, keeps the Mac awake, and opens the Responder and Projector on the laptop. It prints four links. They change every time you start it.

| Link | Who uses it | PIN |
|---|---|---|
| `/j` | Phones: the person walking, the judges | None |
| `/r` | Responder portal, on the laptop | Responder: 2468 |
| `/stage` | Projector, with the Join QR | Responder or presenter PIN |
| `/stage/control` | Presenter's phone | Presenter: 1357 |

Keep the Terminal window open. Closing it, or pressing Ctrl+C, stops everything. The laptop needs internet the whole time.

Anyone with the link can reach the app while it runs, and these PINs are public in our GitHub repo. To change them, edit `RESPONDER_PIN` and `PRESENTER_PIN` in `.env`, then start again.

## Before you record or present

1. Start everything as above.
2. On the phone, open the `/j` link in Chrome (Android) or Safari (iPhone). Allow location when asked. Join.
3. On the Preparing screen, tap **Alert sound tested** and **Location permission**.
4. Tap **Open map**, then pull up the bottom sheet and open **Safety pack** once.
5. Check the responder page shows **1 on trail**.

Do this over the phone's mobile data if the campus Wi-Fi is slow.

## The video: entering CSED

**CSED is red from the moment the app starts**, and again after **Next round**, so nobody can forget to flag it. To film the flagging itself, click **Clear CSED red zone** first, then **Flag CSED red zone** on camera.

1. Stand outside CSED, at least 100 m from the block, for example near the library roundabout. Check the top card shows **GPS ±** and a number.
2. Tap the screen once, so the phone allows sound. Turn the volume up and turn off the iPhone's silent switch.
3. Walk towards the block. Within about 80 m of the red area the phone shows an amber "Red zone: … m ahead" banner.
4. Cross into the red area. On the first GPS reading inside, the phone goes full-screen red with a "You have entered: CSED block" notification card. An alarm repeats and a voice says the warning until you tap a button. It happens about 20 m before the walls, because GPS near a building drifts.
5. Tap **I understand**. A flashing red frame and a red banner stay on for as long as you're inside.
6. Tap **Show safe way back**. A green dashed line points the way out.

**To film it again:** walk back out, wait 20 seconds and walk in again. It alerts on every new entry.

If you're already inside CSED when the app opens, the alert fires as soon as the phone gets its first GPS reading.

**Keep the app open on the screen.** Phones stop web pages when they're locked or in the background, so no alert can fire then. The app keeps the screen on during a trip.

**Notifications:** on Android Chrome, allow notifications and you also get a real system notification. Safari on iPhone doesn't allow them for a web page, so there you get the full-screen alert, the notification card, the alarm and the voice. iPhone vibration isn't available to web pages either.

**If GPS is bad:** pull up the sheet and tap **Simulate walking into CSED**. The dot walks in by itself in about 17 seconds. The warning and alert are the real ones, and only the position is simulated. The screen says so, and you should too.

The simulated walk leaves the phone on a simulated position, and real GPS is ignored until you tap the purple bar at the top or reload the page. The top card tells you which one is on: **GPS ±N m** or **Simulated location**.

## In front of the judges

1. **SOS:** hold the red SOS button for about 2 seconds. Pick **Injured**, then **2–5**, then **Send SOS**. It appears on the responder within seconds.
2. **Accept:** on the responder, open the incident and tap **Accept**. The phone shows **Help acknowledged**, and the projector shows confetti.
3. **Offline pack:** turn on airplane mode. Pull up the sheet and open **Safety pack**. It opens with no signal, and the header says "Saved on this phone".
4. **Offline SOS:** still in airplane mode, send an SOS. It says it's waiting. Turn airplane mode off and it sends itself.
5. **Crowd heatmap:** click **Simulate crowd** on the responder. Over 20 seconds a green-to-red glow fills in around CSED on the responder, the projector and the phones. Say that this crowd is simulated. It stops by itself after 5 minutes, or click **Stop crowd**.
6. **Between rounds:** tap **Next round** on Stage control. It clears everything and shows the Join QR again.

Do the red zone before the crowd. If the person is standing inside the crowd, the phone shows an amber "Dense crowd" alert, which is the app working as designed.

## Why not Vercel

Vercel can host the screens but not the server. SafeTrail needs one always-on program that holds the database, keeps a live connection to every phone and runs the crowd checks. Vercel runs short-lived functions that don't share memory or files, so an SOS could be lost on the way to the responder. Moving it would mean rewriting the backend. For a link that works with the laptop closed, it would need an always-on host such as Render or Railway.

## If something goes wrong

| Problem | Fix |
|---|---|
| "Port 8000 is already in use" | Another copy is running. Close that Terminal window, or run `lsof -ti:8000 \| xargs kill` |
| Phone shows "Turn on location" | Allow location for the browser in the phone's settings, then reload |
| Top card never shows "GPS ±N m" | iPhone: Settings → Privacy & Security → Location Services → turn it on, and set Safari Websites to While Using. Then reload |
| Phone shows old screens | Reload the page twice. The app updates itself after the first load |
| AI text says "Standard text" | The free AI key is busy. That's the safety rule working: everything else still runs |
| The link stopped working | Start again. You get a new link, so scan the new QR on `/stage` |
