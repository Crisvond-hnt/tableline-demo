# Run Tableline in a Switch room

Two parts. The first takes a few minutes in a terminal and needs nothing but Python. The second is the same checks in a Switch channel. No demo video has been recorded.

## Part 1: the checks in a terminal

```bash
git clone https://github.com/Crisvond-hnt/tableline-demo.git
cd tableline-demo
python3 -m unittest discover -s tests -t . -v
python3 -m integrations demo
python3 -m integrations review
```

`demo` prints the fixture night: the conflict with NL-0881, an empty offered list, 21:30 withheld, and the refusal that names NL-1042 and TF-2201. `review` lists the files that were held for staff. Neither writes to `var/`.

To walk the approval path by hand, with a ledger in `var/store.json`:

```bash
python3 -m integrations ingest-mail fixtures/emails/03-cancelled-nl-0770.eml
python3 -m integrations intake fixtures/messages/instagram-party-of-four.json
python3 -m integrations check REQUEST_ID
python3 -m integrations intake fixtures/messages/instagram-follow-up.json
python3 -m integrations approve REQUEST_ID --date 2026-11-14 --time 21:30 --party 4
python3 -m integrations reference REQUEST_ID NL-2044
python3 -m integrations confirm REQUEST_ID
python3 -m integrations pdf --date 2026-11-14 --out exports/northline-2026-11-14.pdf
python3 -m integrations ics --date 2026-11-14 --out exports/northline-2026-11-14.ics
```

`REQUEST_ID` is the id the first `intake` prints. The only notice on this feed is the cancellation of NL-0770, which already had a start and an end, so 21:30 is clear and the approval succeeds once the follow-up moves the request to 21:30. On the full feed (`python3 -m integrations ingest`), the same approval is refused. To see the approval check the feed again, run `python3 -m integrations ingest-mail fixtures/emails/01-new-nl-1042.eml` between `check` and `approve`: the slot was offered, and the approval is still refused, because NL-1042 now has a start and no duration. Delete `var/store.json` to start over.

## Part 2: the room

You need Switch Console, Docker, and one AI coding agent signed in. Claude Code, Codex, or OpenCode all work; the steps below say Claude Code.

### First time only

1. Open Docker Desktop and wait until it says it is running.
2. Sign in to Claude Code in a terminal: `claude auth login`. Follow the browser prompt.
3. Open **Switch Console**. At the bottom of the sidebar, select **Settings**, then **Agent providers**. Claude Code should read **Signed in**. If it reads **CLI not installed**, quit Switch Console fully and open it again; it reads your PATH once at start.
4. Select **Add a server**, then **Run a server on this computer**. Wait for **Docker is ready**, select **Start**. The first start downloads a few GB. When the sidebar reads **Running locally**, the server is up.
5. On the server's **Home** page, under **Messaging apps**, open the menu on the **Mattermost** row, select **Sign-in details…**, then **Open in Mattermost**, and sign in. Switch links that account to you. Mattermost is the chat app for the demo; a channel there is a room like any other.

### Import the template and create the room

1. In the sidebar, select **Templates**, then **Import template**. Choose `templates/tableline.template.yaml` from your clone.
2. Select **Use**.
3. Fill the form:
   - **team**: a short lowercase name, such as `northline`. It prefixes the three agents and the channel.
   - **Repository**: `https://github.com/Crisvond-hnt/tableline-demo.git`. A git URL, never a folder on your laptop. The coordinator clones it into its own working directory.
   - **Provider**: the agent that reads **Signed in**. The form starts from Claude Code, then Codex, then OpenCode.
   - **Bridge**: the messaging app you signed in to. For a local server that is the Mattermost connection.
   - **Location** is folded under Advanced and stays `local`.
4. Select **Create**. Switch creates `northline-coordinator`, `northline-booking`, `northline-guest`, and a private channel `northline-reservations` with you as the only person in it. The kickoff message asks each agent to say its job in one line.

If **Create** stays disabled, the form names the empty field. If Switch says **Nothing was created**, the agent card says why; the usual reason is a provider that is not signed in or a bridge that is not connected.

### Demo in the channel

Open the channel in Mattermost or in Switch Console; both show the same conversation. Say each line, and give the coordinator time to answer.

All three agents answer only the person who created the room and that person's agents. If the coordinator replies `I only take instructions from my owner`, your Mattermost account is not linked to your Switch user yet: in Switch Console, open the server's **Home** page, link the account under **Messaging apps**, and send the line again. Do not widen the agent's addressing to get past it; the restriction is what keeps APPROVE to the owner.

```text
@northline-coordinator Mara wants four people tonight at 8. Can we take it?
```

The reply should sound like a person, not a log. Mara at 8 is taken by NL-0881, seated from 7:30 to 9. 9:30 is not offered, because NL-1042 and TF-2201 have no finish time. Nothing was written and Mara was not told. The first time, the coordinator clones the repository into its own folder before it answers.

The template creates the agents with Auto mode off, so the agent posts a permission request in the thread before each command, including the clone and every file it reads while it learns the repository. Answer each with **Approve** on the request itself; a typed reply such as `A1 1` is also forwarded to the agent as a message. On Claude Code or Codex you can instead open the coordinator's page under **Your Agents** and turn on **Auto mode**: the provider's own review then runs reads and the Tableline commands in the agent's folder without asking, and the owner's word in the room stays the gate for `approve`, `reference`, and `confirm`. Leave Auto mode off on OpenCode, where it approves everything. Do not turn on **Bypass permissions**.

```text
@northline-booking What would you do?
@northline-guest Can we reply to her?
@northline-coordinator What did you hold back?
```

`review` reads the ledger in the coordinator's folder, and `demo` leaves nothing there, so `ingest` comes first. On the fixture feed it holds four items: `05-bad-sender.eml`, `06-missing-reservation.eml`, and two TheFork events, one missing its party and one of an unrecognized kind.

The booking and guest agents answer from the coordinator's post. They do not run commands and they do not hold the ledger.

The approval above is a different night from the full sheet. Say it as its own request, and name the date, the time, and the party yourself. The coordinator does not choose the slot. NL-2044 is a note in the room. The reply to the guest is a draft and is not sent.

Useful room commands: `!list-agents` shows the three agents are members, `!agents-status` shows their sessions, `!roles` shows `booking-writer` and `guest-sender`, `!list-documents` shows the `integration` and `approval` room documents.

## Slack, Discord, Teams, or Telegram instead of Mattermost

The template works with any messaging app that lets Switch create a channel. Connect the app on the server's **Home** page under **Messaging apps**, select **Connect**, and choose the app. Then pick that connection as **Bridge** when you use the template.

- **Slack**: create a Slack app from the manifest in [Connect Slack](https://docs.switchagents.ai/switch-rooms/deploy/messaging-apps/slack), generate the `xapp-` app-level token, install it and copy the `xoxb-` bot token, note the workspace id starting with `T`, and paste the three into the Connect form. Your workspace must allow custom apps. Link your Slack account when asked.
- **Discord** and **Microsoft Teams**: see [messaging apps](https://docs.switchagents.ai/switch-rooms/deploy/messaging-apps/index). Teams needs a server the internet can reach.
- **Telegram**: a Telegram bot cannot create a group, so the template's **Bridge** field will not accept a Telegram connection. To use Telegram, create the group yourself, add the bot, and invite the three agents to the room Switch creates for it. See [Connect Telegram](https://docs.switchagents.ai/switch-rooms/deploy/messaging-apps/telegram).

Everything in the room is synthetic. No booking platform, mailbox, or guest is contacted.
