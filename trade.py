private_key = ""

from collections import defaultdict
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from eth_account import Account
from py_clob_client.exceptions import PolyApiException


def get_all_markets(client):
    data = []
    next_cursor = ""
    while True:
        resp = client.get_sampling_markets(next_cursor=next_cursor)
        for x in resp['data']:
            data.append(x)
        next_cursor = resp['next_cursor']
        if next_cursor == 'LTE=':
            break
    return data


def get_market_prices(client, yes_token_id, no_token_id):
    try:
        yes_price_response = client.get_price(token_id=yes_token_id, side="buy")
        no_price_response = client.get_price(token_id=no_token_id, side="sell")

        yes_price = float(yes_price_response['price']) if yes_price_response else None
        no_price = float(no_price_response['price']) if no_price_response else None

        return yes_price, no_price

    except Exception as e:
        print(f"Error getting market prices: {e}")
        return None, None


def get_order_book_liquidity(client, token_id):
    try:
        order_book = client.get_order_book(token_id)
        total_bids = sum(float(bid.size) for bid in order_book.bids)
        total_asks = sum(float(ask.size) for ask in order_book.asks)

        # Calculate total USD value on order books
        total_bids_usd_value = sum(float(bid.size) * float(bid.price) for bid in order_book.bids)
        total_asks_usd_value = sum(float(ask.size) * float(ask.price) for ask in order_book.asks)

        return total_bids, total_asks, total_bids_usd_value, total_asks_usd_value

    except PolyApiException as e:
        if e.status_code == 404:
            print(f"No orderbook exists for token id {token_id}, skipping.")
            return None, None, None, None
        else:
            raise


def calculate_trade_metrics(size, price, win_probability):
    potential_profit = size * (1 - price)
    potential_loss = size  # total bet size is the loss if the bet fails
    risk_reward_ratio = potential_profit / potential_loss if potential_loss != 0 else 0
    expected_value = (win_probability * potential_profit) - ((1 - win_probability) * potential_loss)
    return potential_profit, potential_loss, risk_reward_ratio, expected_value


def normalize_probabilities(yes_price, no_price):
    # check if either price is zero to avoid division by zero
    if yes_price == 0 or no_price == 0:
        raise ValueError("Cannot normalize probabilities when either yes_price or no_price is zero.")

    total_inverse = 1 / yes_price + 1 / no_price
    normalized_yes_prob = (1 / yes_price) / total_inverse
    normalized_no_prob = (1 / no_price) / total_inverse
    return normalized_yes_prob, normalized_no_prob


def main():
    host = "https://clob.polymarket.com/"
    chain_id = 137  # Polygon mainnet

    # generate a wallet using the private key
    account = Account.from_key(private_key)
    address = account.address
    client = ClobClient(host=host, key=private_key, chain_id=chain_id)

    # create or derive API credentials
    try:
        api_creds = client.create_or_derive_api_creds()
        print("API Key:", api_creds.api_key)
        print("Secret:", api_creds.api_secret)
        print("Passphrase:", api_creds.api_passphrase)

        # Set API credentials for Level 2 authentication
        client.set_api_creds(api_creds)

    except Exception as e:
        print("Error creating or deriving API credentials:", e)
        return

    # Option to choose trading strategy: 'unlikely' or 'likely'
    trade_strategy = 'unlikely'  # Change to 'unlikely' to trade on unlikely outcomes

    # Fetch all available markets using the get_all_markets function
    markets = get_all_markets(client)

    print(f"Total number of available markets: {len(markets)}")

    # Dictionary to track the number of markets at each Minimum Order Size
    min_order_size_count = defaultdict(int)

    order_size_usd = 1.0
    total_potential_profit = 0.0
    total_potential_loss = 0.0
    total_risk_reward_ratio = 0.0
    total_expected_value = 0.0
    trade_count = 0  # To track the number of trades

    for market in markets:
        condition_id = market['condition_id']
        tokens = market['tokens']
        minimum_order_size = market['minimum_order_size']
        start_date = market.get('start_date_iso')
        end_date = market.get('end_date_iso')
        is_active = market.get('active')

        # Update the dictionary with the count of markets per Minimum Order Size
        min_order_size_count[minimum_order_size] += 1

        print(f"Market ID: {condition_id}")
        print(f"Tokens: {tokens}")
        print(f"Minimum Order Size: {minimum_order_size}")
        print(f"Start Date: {start_date}, End Date: {end_date}")
        print(f"Active: {is_active}")

        if not is_active:
            continue  # Skip markets that are not active

        if len(tokens) != 2:
            continue  # Skip markets that are not YES/NO

        yes_token_id = tokens[0]['token_id']
        no_token_id = tokens[1]['token_id']

        # Get the best prices for YES and NO
        yes_price, no_price = get_market_prices(client, yes_token_id, no_token_id)
        if yes_price is None or no_price is None:
            continue

        try:
            # Normalize the probabilities to ensure they sum to 1
            win_probability_yes, win_probability_no = normalize_probabilities(yes_price, no_price)
        except ValueError as e:
            print(f"Skipping market {condition_id} due to error: {e}")
            continue

        # Get liquidity levels for the YES and NO tokens, including their USD values
        yes_liquidity, no_liquidity, yes_liquidity_usd, no_liquidity_usd = get_order_book_liquidity(client,
                                                                                                    yes_token_id)
        if yes_liquidity is None or no_liquidity is None:
            continue  # Skip if no liquidity information is available

        print(f"Yes Liquidity: {yes_liquidity} tokens (${yes_liquidity_usd:.2f} USD)")
        print(f"No Liquidity: {no_liquidity} tokens (${no_liquidity_usd:.2f} USD)")
        print(f"Yes Price: {yes_price}, No Price: {no_price}")
        print("\n----------------------------")

        # Strategy based on selected trading strategy
        if trade_strategy == 'likely':
            # Bet on the more favorable outcome with lower odds (likely)
            if yes_price > no_price and 0.001 < yes_price < 1.0:
                if yes_liquidity >= minimum_order_size:
                    yes_size = max(order_size_usd / yes_price, minimum_order_size)
                    potential_profit, potential_loss, risk_reward_ratio, expected_value = calculate_trade_metrics(
                        yes_size, yes_price, win_probability_yes
                    )

                    total_potential_profit += potential_profit
                    total_potential_loss += yes_size
                    total_risk_reward_ratio += risk_reward_ratio
                    total_expected_value += expected_value
                    trade_count += 1  # Increment trade count

                    print(f"Potential Profit on YES: ${potential_profit:.2f}")
                    print(f"Total Bet Size for YES: ${yes_size:.2f}")
                    print(f"Risk-Reward Ratio: {risk_reward_ratio:.2f}")
                    print(f"Expected Value: ${expected_value:.2f}")

                    order_args = OrderArgs(
                        price=yes_price,
                        size=yes_size,
                        side=BUY,
                        token_id=yes_token_id,
                    )

                    signed_order = client.create_order(order_args)
                    # place the order
                    # resp = client.post_order(signed_order, OrderType.GTC)
                    # print(f"Placed {yes_size} order on YES outcome for market {condition_id} at odds {yes_price} - Response: {resp}")

            elif no_price > yes_price and 0.001 < no_price < 1.0:
                if no_liquidity >= minimum_order_size:
                    no_size = max(order_size_usd / no_price, minimum_order_size)
                    potential_profit, potential_loss, risk_reward_ratio, expected_value = calculate_trade_metrics(
                        no_size, no_price, win_probability_no
                    )

                    total_potential_profit += potential_profit
                    total_potential_loss += no_size
                    total_risk_reward_ratio += risk_reward_ratio
                    total_expected_value += expected_value
                    trade_count += 1  # Increment trade count

                    print(f"Potential Profit on NO: ${potential_profit:.2f}")
                    print(f"Total Bet Size for NO: ${no_size:.2f}")
                    print(f"Risk-Reward Ratio: {risk_reward_ratio:.2f}")
                    print(f"Expected Value: ${expected_value:.2f}")

                    order_args = OrderArgs(
                        price=no_price,
                        size=no_size,
                        side=BUY,
                        token_id=no_token_id,
                    )

                    signed_order = client.create_order(order_args)
                    # place the order
                    # resp = client.post_order(signed_order, OrderType.GTC)
                    # print(f"Placed {no_size} order on NO outcome for market {condition_id} at odds {no_price} - Response: {resp}")

        elif trade_strategy == 'unlikely':
            # Bet on the less favorable outcome with higher odds (unlikely)
            if yes_price < no_price and 0.001 < yes_price < 1.0:
                if yes_liquidity >= minimum_order_size:
                    yes_size = max(order_size_usd / yes_price, minimum_order_size)
                    potential_profit, potential_loss, risk_reward_ratio, expected_value = calculate_trade_metrics(
                        yes_size, yes_price, win_probability_yes
                    )
                    total_potential_profit += potential_profit
                    total_potential_loss += yes_size
                    total_risk_reward_ratio += risk_reward_ratio
                    total_expected_value += expected_value
                    trade_count += 1  # Increment trade count

                    print(f"Potential Profit on YES: ${potential_profit:.2f}")
                    print(f"Total Bet Size for YES: ${yes_size:.2f}")
                    print(f"Risk-Reward Ratio: {risk_reward_ratio:.2f}")
                    print(f"Expected Value: ${expected_value:.2f}")

                    order_args = OrderArgs(
                        price=yes_price,
                        size=yes_size,
                        side=BUY,
                        token_id=yes_token_id,
                    )
                    signed_order = client.create_order(order_args)
                    # place the order
                    # resp = client.post_order(signed_order, OrderType.GTC)
                    # print(f"Placed {yes_size} order on YES outcome for market {condition_id} at odds {yes_price} - Response: {resp}")

            elif no_price < yes_price and 0.001 < no_price < 1.0:
                if no_liquidity >= minimum_order_size:
                    no_size = max(order_size_usd / no_price, minimum_order_size)
                    potential_profit, potential_loss, risk_reward_ratio, expected_value = calculate_trade_metrics(
                        no_size, no_price, win_probability_no
                    )
                    total_potential_profit += potential_profit
                    total_potential_loss += no_size
                    total_risk_reward_ratio += risk_reward_ratio
                    total_expected_value += expected_value
                    trade_count += 1  # Increment trade count

                    print(f"Potential Profit on NO: ${potential_profit:.2f}")
                    print(f"Total Bet Size for NO: ${no_size:.2f}")
                    print(f"Risk-Reward Ratio: {risk_reward_ratio:.2f}")
                    print(f"Expected Value: ${expected_value:.2f}")

                    order_args = OrderArgs(
                        price=no_price,
                        size=no_size,
                        side=BUY,
                        token_id=no_token_id,
                    )
                    signed_order = client.create_order(order_args)
                    # place the order
                    # resp = client.post_order(signed_order, OrderType.GTC)
                    # print(f"Placed {no_size} order on NO outcome for market {condition_id} at odds {no_price} - Response: {resp}")

    # Calculate average risk-reward ratio
    average_risk_reward_ratio = total_risk_reward_ratio / trade_count if trade_count > 0 else 0

    print("Number of markets at each Minimum Order Size:")

    for min_order_size, count in min_order_size_count.items():
        print(f"Minimum Order Size: {min_order_size} - Number of Markets: {count}")

    print(f"Total Potential Profit if all trades succeed: ${total_potential_profit:.2f}")
    print(f"Total Bet Size (Total Potential Loss if all trades fail): ${total_potential_loss:.2f}")
    print(f"Average Risk-Reward Ratio: {average_risk_reward_ratio:.2f}")
    print(f"Cumulative Expected Value: ${total_expected_value:.2f}")
    print("Done placing orders.")


if __name__ == "__main__":
    main()
