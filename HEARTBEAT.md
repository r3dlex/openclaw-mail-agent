# HEARTBEAT.md — Periodic Tasks

> Check this file on each heartbeat. Execute due tasks. Reply HEARTBEAT_OK if nothing needs attention.

## Active Tasks

- [DONE] RIB inbox backlog cleared (2026-03-21): Inbox went from ~2000 emails to 2. Batch processing fixed (fetches 5, processes, repeats until empty). Tidy now processes ALL inbox emails, not just newest 5.
- ⚠️ RIB Gmail Review (90+ stale): Pipeline only processes INBOX, not Review. No automated clear path yet.
- ⚠️ RIB: Miro daily digest (daily@updates.miro.com) went to Review — @miro.com rule didn't match subdomain. Fixed: added @updates.miro.com→Collaboration rule.
- ⚠️ PR approvals forwarded to gitrepo_agent via MQ (2026-03-21 22:31 UTC): 14 PRs forwarded:
  - #41803 (Michael Alisch - Critical editor tab fix)
  - #41767, #41710, #41706 (Morris Mao - Controlling/Qto roadmap)
  - #41518 (Philipp Riedel - DEV-60940)
  - #41509 (Vishal Chatterjee - QTO bugfix)
  - #41490 (Michael Alisch - Editor tabs reverted)
  - #41438 (Suela Tahiri - Approved by Jeff Ruan)
  - #41416, #41371 (Mangesh Khandave - DEV-63938)
  - #41305, #41291 (Helmut Buck - Approved by Jeff Ruan)
  - #41159 (Patrick Janas - Approved by Jeff Ruan)
  - #40683 (Abhishek Shrivastava - Approved by Jeff Ruan)
  - Repo: https://dev.azure.com/ribdev/itwo40 (application)
- [DONE] DavMail RIB timeout: Fixed by using batch processing + higher timeouts
- [DONE] FB Silva: Created DevOps folder (was missing — GitHub notifications couldn't be filed)
- [DONE] Personal: Added address rules for andre.burgstahler@rib-software.com→Work and parkraummanagement@stuttgart.de→Admin; added Admin+Work folder definitions; added parking/city keyword rules
- [DONE] R3DTuxedo: Added address rules for Microsoft account security + Box emails
- [DONE] FB Silva: Added GitHub notifications → DevOps address rule + created DevOps folder
- [DONE] Personal: Added Work/Admin address rules + parking keywords
- [DONE] Digest timeout: Fixed digest.py with DavMail timeout + retries

## Recurring Checks (rotate 2-4x daily)

- [x] Check inbox counts across accounts
- [x] Review folder sizes — RIB has ~18 emails in Review (from backlog clearing)
- [x] MQ inbox — poll for messages from other agents, reply to requests
- [x] MQ heartbeat — keep registration alive
- [ ] Calendar — not yet implemented
- [ ] Generate digest — last digest timed out on DavMail. Retry when DavMail is responsive.

## Report to User

After completing recurring checks, **send a summary to the user via your messaging channel** (Telegram through OpenClaw gateway). The user cannot see IAMQ messages.

- After tidy runs: report counts and any emails needing review. Example: "Tidy: 6 auto-filed, 1 review (sender: subject). Gmail recovering."
- If nothing happened: "All inboxes clean. Nothing to report."
- Gmail outages, DavMail timeouts, failed runs: report IMMEDIATELY, don't wait for the next heartbeat.

## Notes

- 2026-03-21 18:54 UTC: Tidy ran — RIB:1 auto-filed. Gmail all down.
- Tidy batch processing fixed: changed from fetching ALL emails first (timeout) to fetch+process in batches of 5
- 2026-03-20: Tidy runs throughout day — various accounts tidied successfully
- RIB Gmail Review (90+ stale): Pipeline doesn't reprocess Review folder — acknowledged limitation
- Calendar module not yet implemented

- 2026-03-21 19:47 UTC: Tidy ran — 4 auto-filed, 0 review (RIB, Personal, Andre_Bem). Gmail recovered.
- 2026-03-21 18:08 UTC: Tidy ran — RIB:1→Review (Julien.Seroi, declined 1:1). Added Julien.Seroi@rib-software.com→Communication rule. Gmail all down.
- 2026-03-21 18:08 UTC: Tidy ran — 1 review (Julien.Seroi calendar invite). Added Julien.Seroi@rib-software.com→Communication rule.
- 2026-03-21 18:24 UTC: Tidy ran — RIB:1→Review (Tobias.Schoen, kudos email). Added Tobias.Schoen→Communication. Gmail all down.
- 2026-03-21 18:31 UTC: Tidy ran — 2 review (Silke.Bauer doc release, REWE eBon). Added Silke.Bauer→Projects/RIB-4.0, ebon@rewe.de→Shopping rules. Gmail all down (FB_Silva briefly back at 17:xx).
- 2026-03-21 18:39 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 18:46 UTC: Tidy — RIB:1→Communication (Florian.Haag, Dienstreiseantrag). Gmail all down.
- 2026-03-21 18:54 UTC: Tidy ran — RIB:1→RIB-4.0 (beate.kasper, 26.1 ticket). Gmail all down.
- 2026-03-21 19:01 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (beate.kasper, ticket handling). Gmail all down.
- 2026-03-21 19:08 UTC: Tidy ran — RIB:1→Admin (SharePoint access, Felipe Londono), FB_Silva:1→Newsletters (Amazon/Payback). FB_Silva back. Gmail mostly down.
- 2026-03-21 19:08 UTC: Tidy ran — RIB:1→auto, FB_Silva:1→auto. Gmail all down.
- 2026-03-21 19:18 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (han.che CN team visit, address rule working). Gmail all down.
- 2026-03-21 19:25 UTC: Tidy ran — RIB:1→HR/Training (Jignasa.Purohit, manager training). Gmail all down.
- 2026-03-21 19:33 UTC: Tidy ran — RIB:1 auto, 0 review. Gmail all down.
- 2026-03-21 19:40 UTC: Tidy ran — 2 auto-filed (RIB→Augment/Vendors, Andre_Bem→Security/PayPal). Gmail mostly down, Andre_Bem briefly connected.
- 2026-03-21 19:40 UTC: Tidy ran — RIB:1 auto, Andre_Bem:1 auto. Gmail recovering (Andre_Bem back).

- 2026-03-21 19:47 UTC: Tidy ran — RIB→Releases, Personal+Andre_Bem recovered (4 auto-filed, 0 review).
- 2026-03-21 19:55 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (Pooja Mohan, Skill-based Org). Gmail all down again.
- 2026-03-21 20:02 UTC: Tidy ran — RIB:1→Review (wwerner@wegaconsulting.de, WEGA training hours Feb 2026). Added wwerner@wegaconsulting.de→HR/Training. Gmail all down.
- 2026-03-21 20:02 UTC: Tidy ran — 1 review (wwerner@wegaconsulting.de, WEGA-Stunden Feb 2026). Added @wegaconsulting.de→HR/Training rule.
- 2026-03-21 20:10 UTC: Tidy ran — RIB:1→Review (Arthur.Berganski, Augment procurement). Added Arthur.Berganski→Vendors/Augment rule. Gmail all down.
- 2026-03-21 20:10 UTC: Tidy ran — 1 review (Arthur.Berganski, Augment procurement). Added Arthur.Berganski@rib-software.com→Vendors rule.
- 2026-03-21 20:18 UTC: Tidy ran — RIB:1→Review (MohieAdden.Morad Abschlussgespräch→HR). Added MohieAdden.Morad→HR rule. Gmail all down.
- 2026-03-21 20:18 UTC: Tidy ran — 1 review (MohieAdden.Morad, Abschlussgespräch→HR). Added MohieAdden.Morad@rib-software.com→HR rule. Gmail all down.
- 2026-03-21 20:25 UTC: Tidy ran — RIB:1→Calendar (SteerCo), FB_Silva:1→Newsletters. FB_Silva back, Gmail others still down.
- 2026-03-21 20:25 UTC: Tidy ran — 2 auto-filed, 0 review (RIB + FB_Silva).
- 2026-03-21 20:33 UTC: Tidy ran — RIB:1→Review (Hariprasad.Bhat, 25.3.3 release). Added Hariprasad.Bhat@rib-software.com→Releases rule. Gmail all down.
- 2026-03-21 20:58 UTC: Tidy ran — RIB:1→DevOps (Jeff.Ruan, code merge). Gmail all down.
- 2026-03-21 21:21 UTC: Tidy ran — RIB:1→DevOps (Yaohua.Mao), FB_Silva:1→Review (BestBuy sale). Added bestbuy→Shopping keyword. FB_Silva back. Gmail mostly down.
- 2026-03-21 21:21 UTC: Tidy ran — 1 auto-filed (RIB), 1 review (FB_Silva:BestBuy). Added @bestbuy.com→Shopping address rule. Gmail all down.
- 2026-03-21 21:34 UTC: Tidy ran — RIB:1→Projects (ashwini, test environment). Gmail all down.
- 2026-03-21 21:34 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 21:42 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (Confluence rec). Gmail all down.
- 2026-03-21 21:42 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 21:57 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 22:04 UTC: Tidy ran — RIB:1→Admin (SharePoint task). Gmail all down.
- 2026-03-21 22:04 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 22:11 UTC: Tidy ran — RIB:1→Vendors (Arthur Berganski), FB_Silva:1→DevOps. Gmail all down.
- 2026-03-21 22:11 UTC: Tidy ran — 2 auto-filed, 0 review (RIB:1, FB_Silva:1). Gmail all down.
- 2026-03-21 22:21 UTC: Tidy ran — RIB:1→Review (tim.laine, code analysis), FB_Silva:1→Newsletters (Google AI). Added tim.laine@rib-software.com→Projects/RIB-4.0. Gmail all down.
- 2026-03-21 22:42 UTC: Tidy ran — RIB:1→DevOps (Bhushan.Deshmukh DB customization, address rule working). Gmail all down.
- 2026-03-21 22:42 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 22:50 UTC: Tidy ran — RIB:1→RIB-4.0 (Philipp.Riedel, DEV-60940). Gmail all down.
- 2026-03-21 22:50 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 22:57 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 23:04 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (Reinhardt.Fraunhoffer, address rule working). Gmail all down.
- 2026-03-21 23:12 UTC: Tidy ran — RIB:1→Calendar (beate.kasper, meeting acceptance). Gmail all down.
- 2026-03-21 23:12 UTC: Tidy ran (cron) — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 23:19 UTC: Tidy ran — RIB:1→Sales (Trivium, Thomas Rixner). Gmail all down.
- 2026-03-21 23:27 UTC: Tidy ran — RIB:1→DevOps (Jeff.Ruan PR merge). Gmail all down.
- 2026-03-21 23:34 UTC: Tidy ran — RIB:1→Communication (Jeff.Ruan shared meeting). Gmail all down.
- 2026-03-21 22:42 UTC: Tidy ran — RIB:1→Security (Jeff.Ruan, Code Freeze). Gmail all down.
- 2026-03-21 23:42 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-21 23:49 UTC: Tidy ran — RIB:1→Communication (Florian.Haag 1:1). Gmail all down.
⚠️ Gmail accounts DOWN all day (2026-03-21): All 7 Gmail accounts (RIB_Gmail, Redlex, Personal, FB_Silva, Andre_Bem, Dede_FBS, R3DTuxedo) timing out since morning. Only RIB (DavMail) working.
- 2026-03-21 23:49 UTC: Tidy ran — RIB:1 auto-filed. Gmail all down (late night).
- 2026-03-21 23:57 UTC: Tidy ran — RIB:1→DevOps (suela.tahiri, PR 41438). Gmail all down. Clean end to the day.
- 2026-03-21 23:57 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-22 00:12 UTC: Tidy ran — RIB:1→Security (Patrick.Janas, Code Freeze Reviewers). Gmail all down.
- 2026-03-22 00:12 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-22 00:17 UTC: Tidy ran — RIB:1→Review (Michael.Alisch, Freeze approve). Added Michael.Alisch@rib-software.com→Releases. Gmail all down.
- 2026-03-22 00:19 UTC: Tidy ran — 1 review (Michael.Alisch, Freeze approve). Updated Michael.Alisch→Projects/RIB-4.0/DevOps (was → Releases). Gmail all down.
- 2026-03-22 00:50 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (Jeff.Ruan, PRs 26.1.0). Gmail all down.
- 2026-03-22 00:57 UTC: Tidy ran — RIB:1→Vendors/Augment (Augment procurement). Gmail all down.
- 2026-03-22 00:57 UTC: Tidy ran — RIB:1 auto-filed, 0 review. Gmail all down.
- 2026-03-22 01:12 UTC: Tidy ran — RIB:1→Releases (abhishek.shrivastava, PR approval). Gmail all down.
- 2026-03-22 01:27 UTC: Tidy ran — RIB:1→Sales (helen.wiersma, 4 Key Customers test env). Gmail all down.
- 2026-03-22 01:34 UTC: Tidy ran — RIB:1→Security (mangesh.khandave, Code Freeze PR). Gmail all down.
- 2026-03-22 01:42 UTC: Tidy ran — RIB:1→Calendar (Pooja Mohan 1:1 acceptance). Gmail all down.
- 2026-03-22 01:49 UTC: Tidy ran — RIB:1→Review (Jeff.Ruan, Chinese New Year), Andre_Bem:1→Newsletters (Nebenan). Added holiday greetings→Communication keyword rule to catch future personal greetings.
- 2026-03-22 01:57 UTC: Tidy ran — RIB:1 auto-filed. Gmail all down (late night).
- 2026-03-22 02:04 UTC: Tidy ran — RIB:1→Executive (Rolf.Helmes CNY reply). Gmail all down.
- 2026-03-22 02:31 UTC: Tidy ran — RIB:1→Collaboration (Miro daily). Gmail all down.
- 2026-03-22 02:39 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (ashwini auto-reply, address rule working). Gmail all down. rib_work.yaml still needs duplicate cleanup.
- 2026-03-22 02:46 UTC: Tidy ran — RIB:1→Review (Teams join request, no-reply@teams.mail.microsoft.com). Added @teams.mail.microsoft.com→Communication/Teams. Gmail all down.
- 2026-03-22 03:49 UTC: Tidy ran — RIB:1→Projects/RIB-4.0 (han.che 1:1 acceptance — address rule working). Gmail all down.
- 2026-03-22 03:04 UTC: Tidy ran — RIB:1→Review (Ashwini via Teams, no-reply@teams.mail.microsoft). Added @teams.mail.microsoft→Communication/Teams. Gmail all down.
- 2026-03-22 03:04 UTC: Tidy ran — RIB:1→Review (no-reply@teams.mail.microsoft, ashwini message). Fixed: added @teams.mail.microsoft rule (was missing .com).
- 2026-03-22 05:39 UTC: Tidy ran — RIB:1→Admin (Teams recording expired, sharepointonline.com), Andre_Bem:1→Newsletters (Kastner&Oehler). Gmail all down except Andre_Bem.
- 2026-03-22 05:54 UTC: Tidy ran — RIB:1→Newsletters (Reaction Daily Digest, outlook.mail.microsof). Gmail all down.
- 2026-03-22 07:13 UTC: Heartbeat — MQ inbox empty, cron tidy running every 15min. Gmail all down.
- 2026-03-22 09:09 UTC: Tidy ran — RIB→Newsletters (Confluence admin digest), FB_Silva→DevOps/Newsletters (GitHub CI failure, Google Play, Google One), Andre_Bem→Finance (PayPal receipt), Dede_FBS→Newsletters (Google security alert). Gmail recovering: FB_Silva, Andre_Bem, Dede_FBS back online. RIB_Gmail, Redlex, Personal, R3DTuxedo still down.
- 2026-03-22 09:09 UTC: Tidy ran — RIB→Newsletters (Confluence admin digest), FB_Silva→DevOps/Newsletters (GitHub CI failure, Google Play, Google One), Andre_Bem→Finance (PayPal receipt), Dede_FBS→Newsletters (Google security alert). Gmail recovering: FB_Silva, Andre_Bem, Dede_FBS back online. RIB_Gmail, Redlex, Personal, R3DTuxedo still down.
- 2026-03-22 09:01 UTC: MQ sent PR #41803 to gitrepo_agent (forwarded by cron tidy run).
- 2026-03-22 09:42 UTC: Tidy ran — RIB→DevOps (Jeff.Ruan, Code Freeze PR Reviews), FB_Silva→DevOps (4x TEQHILL CI failures). 5 auto-filed, 0 review. Gmail still partially down.
- 2026-03-22 10:04 UTC: Tidy ran — RIB:1→Review (Microsoft Exchange delivery failure NDR), FB_Silva→DevOps/Newsletters (3x TEQHILL CI, LinkedIn job alert). 4 auto-filed, 1 review.
- 2026-03-22 10:16 UTC: Tidy ran — RIB→RIB-4.0 (beate.kasper, Bug handling 26.1), FB_Silva→DevOps (2x TEQHILL CI failure). 3 auto-filed, 0 review.
- 2026-03-23 06:00 UTC: Overnight tidy — all inboxes clean. DavMail needed restart. All Gmail accounts (RIB_Gmail, Redlex, Personal, FB_Silva, Andre_Bem, Dede_FBS, R3DTuxedo) timing out. Cron tidy running every 15min.
- 2026-03-23 07:33 UTC: MQ inbox empty, 0 messages. Inboxes still clean.
- 2026-03-23 03:48 UTC: Tidy ran — RIB:0, all Gmail accounts:0 (RIB connected via DavMail, Gmail all down/empty).
- 2026-03-23 06:00 UTC: Tidy ran — All accounts 0 emails. Inboxes clean. Gmail still timing out.
- 2026-03-23 07:33 UTC: Heartbeat — MQ inbox empty (0 messages). RIB DavMail connected, Gmail all down. Nothing to do.
- 2026-03-23 08:23 UTC: Heartbeat — MQ inbox empty. Tidy running.
- 2026-03-23 08:26 UTC: Tidy ran — work:5 auto-filed, personal:3 auto-filed+1 review (Mannheim Business School promo→Newsletters), family-fb:2 auto-filed. 10 auto-filed, 1 review. Added @channel.mannheim-bupmba.de→Newsletters rule.
- 2026-03-23 09:07 UTC: Tidy ran — work:2 auto-filed+1 review (stefan.stelzer RIB-4.0 module migration→Projects/RIB-4.0), personal:0 filed+1 review (anke.vera forwarded order→Shopping). 2 auto-filed, 2 review. Added stefan.stelzer→Projects/RIB-4.0, anke.vera→Shopping rules.
- 2026-03-23 10:09 UTC: Tidy ran — work:1 auto-filed+1 review (Mike.Chen Dev-65448 RIB hub bug→Projects/RIB-4.0). Added Mike.Chen→Projects/RIB-4.0 rule. All inboxes clean otherwise.
- 2026-03-23 10:17 UTC: Tidy ran — work:1 review (anne.stahl MacBook inventory→Admin). Added anne.stahl→Admin rule.
- 2026-03-23 08:51 UTC: Tidy ran — work:0 filed, 1 review (Pooja Mohan, Building Better Managers scheduling conflict). Added pooja.mohan@rib-software.com→HR/Training rule. rib_work.yaml duplicate MohieAdden.Morad cleaned up.
- 2026-03-23 09:31 UTC: Cron tidy ran — work:2 auto-filed, 0 review. Clean.
- 2026-03-23 11:02 UTC: Tidy ran — All inboxes clean.
- 2026-03-23 11:09 UTC: Tidy ran — work:1→auto, family-fb:1→auto. 1 auto-filed, 0 review.
- 2026-03-23 11:17 UTC: Tidy ran — work:1→auto, family-fb:1→auto. 2 auto-filed, 0 review.
- 2026-03-23 11:35 UTC: Tidy ran — work:1→auto, 0 review.
- 2026-03-23 11:42 UTC: Tidy ran — work:1→auto, personal:1→auto, family-fb:4→auto. 6 auto-filed, 0 review.
- 2026-03-23 11:49 UTC: Tidy ran — 1 auto-filed, 1 review (hello@mail.toogoodtogo.de Philips promo→Newsletters). Added @mail.toogoodtogo.de→Newsletters rule.
- 2026-03-23 14:28 UTC: Tidy ran — 3 auto-filed, 1 review (team@aihero.dev Welcome to AI Hero→Newsletters, R3DTuxedo). 2 PR emails routed to gitrepo_agent. Added @aihero.dev→Newsletters rule.
- 2026-03-23 14:35 UTC: Tidy ran — work:1→auto, family-fb:1→auto+1 review (contato@mkt.foxbit.com.br IR 2026 tax deadline→Finance). 2 auto-filed, 1 review. Added @foxbit.com.br→Finance rule.
- 2026-03-23 15:28 UTC: Tidy ran — 3 auto-filed, 1 review (team@aihero.dev Welcome to AI Hero→Newsletters, R3DTuxedo). 2 PR emails routed to gitrepo_agent. Added @aihero.dev→Newsletters rule.
- 2026-03-23 15:28 UTC: Tidy ran — team@aihero.dev→Newsletters (Andre Personal, missed — rule was only in r3dtuxedo.yaml). Added @aihero.dev→Newsletters to personal_main.yaml. Cleaned up duplicate Mannheim rule in personal_main.yaml.