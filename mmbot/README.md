# Intro
The goal of this script is to send a Mattermost message when a transaction is found for that user.

You can subscribe to these messages by adding your Mattermost username (mm_username) to the file `static/members.beancount`

Example:
```
1970-01-01 open Liabilities:Bar:Members:Gust
  mm_name: "gust"
```
This script is called by the Github Actions `.github/workflows/mmbot.yml`. The Action will be triggered for every change in the `ledger/*.beancount` files and will search for the hard-coded commit message "`Automatic commit by backtab`" to assume it is a bar transaction commit.

When a transaction is found the barbot Mattermost account will send a message to the user.