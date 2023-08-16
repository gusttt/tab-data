import sys
import logging
import subprocess
import requests
import json
from pprint import pformat
from beancount import loader


class MattermostAPI:
    def __init__(self, server_url, auth_token):
        self.server_url = server_url
        self.api_endpoint = "api/v4/"
        self.auth_token = auth_token
        self.headers = {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json'
        }


    def mm_view_self(self):
        api_path = "users/me"
        response = requests.get(self.server_url + self.api_endpoint + api_path, headers=self.headers)
        if response.status_code == 200:
            logging.debug('Response mm_view_self:\n %s', pformat(response.json()))
            user = response.json()
            return user['id']
        else:
            logging.error("Error mm_view_self: %s", response.text)


    def mm_search_userid(self, user_name):
        api_path = "users/search"
        data = { "term": user_name }

        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 200:
            logging.debug('Response mm_search_userid:\n %s', pformat(response.json()))            
            user = response.json()
            return user[0]['id']
        else:
            logging.error("Error mm_search_userid: %s", response.text)


    def mm_get_channel_id(self,bot_id,tx_user_id):
        api_path = "channels/direct"
        data = [bot_id, tx_user_id]

        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 201:
            logging.debug('Response mm_get_channel_id:\n %s', pformat(response.json()))
            channel_id = response.json()
            return channel_id['id']
        else:
            logging.error("Error mm_get_channel_id: %s", response.text)


    def mm_direct_message(self, channel_id, msg):
        api_path = "posts"
        data = {
            "channel_id": channel_id,
            "message": msg
        }
        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 201:
            logging.info('Response mm_direct_message:\n %s', pformat(response.json()))
        else:
            logging.error("Error: Failed to post direct message. Status code: %s %s", response.status_code, response.text)


def get_mm_user(user):
    member_name = user
    # Load the members data from the 'members.beancount' file
    members_file = "./static/members.beancount"
    with open(members_file, "r") as f:
        members_data = f.read()
    # Parse the members data using beancount
    members_entries, _, _ = loader.load_string(members_data)
    # Find and extract the mm_name for the target member
    mm_name = None
    for member_entry in members_entries:
        logging.debug('Entry: %s', member_entry)
        logging.debug('Account: %s', member_entry.account)
        logging.debug('Display name: %s', member_entry.meta.get("display_name"))
        if (
            member_entry.__class__.__name__ == "Open" and
            member_entry.account == f"Liabilities:Bar:Members:{member_name}" or
            member_entry.meta.get("display_name") == f"{member_name}"
        ):
            mm_name = member_entry.meta.get("mm_name")
            break

    if mm_name:
        logging.info('Mattermost user for %s is: %s', member_name, mm_name)
        return mm_name
    else:
        logging.info('Mattermost user (mm_name) not found for %s in members.beancount. Stopping here.', member_name)
        sys.exit()


def get_user_from_tx(added_transactions):
    # Parse the transaction using beancount
    tx_entries, _, _ = loader.load_string(added_transactions)

    # Extract the member name from the transaction description
    transaction_description = tx_entries[0].narration
    member_name = transaction_description.split(" ")[0]
    return member_name


def extract_added_transactions_from_git_show():
    result = subprocess.run(['git', 'show'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    lines = output.splitlines()
    tx = ""
    for line in lines:
        if line.startswith('+'):
            if line.startswith('++'):
                continue
            tx = tx + line.lstrip('+') + '\n'
    return tx


if __name__ == '__main__':
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', level='INFO')
    logging.info('Starting script %s', __file__)

    # Hardcoded from github actions yml
    mm_url = sys.argv[1]
    token = sys.argv[2]

    # Check if the commit is transaction 
    result = subprocess.run(['git', 'log','-1','--format=%s'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8').rstrip()
    if output != "Automatic commit by backtab":
        logging.info("Commit msg does not match 'Automatic commit by backtab', assuming not a transaction. Stopping here.")
        sys.exit(0)

    added_transactions = extract_added_transactions_from_git_show()
    logging.info('Git commit msg:\n %s', added_transactions)
    member_name = get_user_from_tx(added_transactions)
    logging.info('Membername from transaction: %s', member_name)
    mm_user = get_mm_user(member_name)

    api = MattermostAPI(mm_url, token)
    # Setup mattermost direct message channel between barbot and transaction user
    barbot_user_id = api.mm_view_self()
    logging.info('Barbot mm user_id: %s', barbot_user_id)
    tx_user_id = api.mm_search_userid(mm_user)
    logging.info('%s mm user_id: %s', mm_user, tx_user_id)
    direct_channel_id = api.mm_get_channel_id(barbot_user_id, tx_user_id)
    logging.info('Direct mm channel id: %s', direct_channel_id)
    # Send mattermost msg
    msg = "Bar transaction found for user " + member_name + ":\n" + added_transactions
    api.mm_direct_message(direct_channel_id, msg)
    
    logging.info('Done.')
