<a id="readme-top"></a>
<!-- PROJECT SHIELDS -->
[![Python][python-shield]][python-url]
[![Poetry][poetry-shield]][poetry-url]
[![Github Sponsors][github-sponsors-shield]][github-sponsors-url]
[![Buy Me A Coffee][buy-me-a-coffee-shield]][buy-me-a-coffee-url]

<br />
<div align="center">

# GhostCompanion

Transfer transactions from numerous sources to [Ghostfolio](https://github.com/ghostfolio/ghostfolio).

Currently implemented for [Binance](https://www.binance.com), [Coinbase](https://coinbase.com),
[Interactive Brokers (IBKR)](https://www.interactivebrokers.com), [Tastytrade](https://tastytrade.com)
and self-custody Bitcoin, Ethereum and Base wallets.
<br />
<br />
[Getting Started](#getting-started) •
[Report Bug](https://github.com/OliRafa/ghostcompanion/issues/new?labels=bug&template=bug-report---.md) •
[Request Feature](https://github.com/OliRafa/ghostcompanion/issues/new?labels=enhancement&template=feature-request---.md) •
[Roadmap](#roadmap)
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
<!-- mtoc-start -->

* [Getting Started](#getting-started)
  * [Environment Variables](#environment-variables)
  * [Configuration File](#configuration-file)
  * [Self-Hosted Ghostfolio Currencies](#self-hosted-ghostfolio-currencies)
  * [Docker](#docker)
  * [Docker Compose](#docker-compose)
  * [Kubernetes](#kubernetes)
* [Self-Custody Wallets](#self-custody-wallets)
  * [Ethereum and Base Wallets](#ethereum-and-base-wallets)
* [Binance Exports and Caveats](#binance-exports-and-caveats)
* [Interactive Brokers Flex Queries and Caveats](#interactive-brokers-flex-queries-and-caveats)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
  * [Continuous Integration](#continuous-integration)
  * [Local Ghostfolio](#local-ghostfolio)
  * [Top contributors](#top-contributors)
* [Acknowledgments](#acknowledgments)
* [License](#license)

<!-- mtoc-end -->
</details>

## Getting Started

GhostCompanion plugin works best when doing account management all by itself.
In other words, manually creating activities in your Ghostfolio account
is not only not needed, but it's also discouraged.
That's because some operations (like symbol change, or stock splits)
need to understand the complete picture of the account, and change its state
totally (see [Interactive Brokers Flex Queries and Caveats](#interactive-brokers-flex-queries-and-caveats)
for the only exception).

It'll start by getting (or creating) accounts for each source
(`Binance`, `Coinbase`, `Interactive Brokers`, `Tastytrade`, or each
[self-custody wallet](#self-custody-wallets) by its name) from Ghostfolio,
and from that it'll start adding trading transactions and/or dividends.

This plugin runs completely in the background, and is provided as
container images hosted on
[Docker Hub](https://hub.docker.com/r/olirafa/ghostcompanion) for `linux/amd64`.

### Environment Variables

Start by setting up the appropriate environment variables, listed below.

| Name                       | Type                | Default Value         | Description                                                                                                                                                             |
| -------------------------- | ------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ALCHEMY_API_KEY`          | `string` (optional) |                       | [Alchemy](https://www.alchemy.com) API key (the free plan is enough), with Ethereum and Base enabled. Needed to read [EVM wallets](#ethereum-and-base-wallets). |
| `BINANCE_API_KEY`          | `string`            |                       | The _Binance_ API Key, with only "Enable Reading" on. See [Binance Exports and Caveats](#binance-exports-and-caveats). |
| `BINANCE_SECRET`           | `string`            |                       | The _Binance_ API Secret Key. |
| `COINBASE_API_KEY_ID`      | `string`            |                       | The _Coinbase_ API Key.                                                                                                                                         |
| `COINBASE_SECRET`          | `string`            |                       | The _Coinbase_ Secret. It must be generated according to the <a href="https://docs.cdp.coinbase.com/coinbase-app/authentication-authorization/api-key-authentication#creating-api-keys" target="_blank">Coinbase API official documentation</a>.|
| `GHOSTCOMPANION_CONFIG`    | `string` (optional) | `ghostcompanion.yaml` | Path to the [configuration file](#configuration-file), relative to the working directory (`/app` in the container). |
| `GHOSTFOLIO_ACCOUNT_TOKEN` | `string`            |                       | The _Ghostfolio_ Account Token.                                                                                                                                         |
| `GHOSTFOLIO_BASE_URL`      | `string` (optional) | "<https://ghostfol.io>" | The _Ghostfolio_ URL. If you're self hosting you should change it for your particular instance URL, otherwise all data will be exported to _Ghostfolio_ cloud offering. |
| `IBKR_QUERY`               | `string`            |                       | The _Interactive Brokers_ Flex Query ID.                                                                                                                                              |
| `IBKR_TOKEN`               | `string`            |                       | The _Interactive Brokers_ Flex Query Token.                                                                                                                                              |
| `TASTYTRADE_CLIENT_SECRET` | `string`            |                       | The _Tastytrade_ Client Secret.                                                                                                                                              |
| `TASTYTRADE_REFRESH_TOKEN` | `string`            |                       | The _Tastytrade_ Refresh Token.                                                                                                                                              |
| `LOG_LEVEL`                | `string` (optional) | `INFO`                | Logging verbosity: DEBUG, INFO, WARNING, ERROR, or CRITICAL. |
| `MEMPOOL_BASE_URL`         | `string` (optional) | "<https://mempool.space/api>" | Esplora-compatible API used to read [self-custody wallets](#self-custody-wallets) from the blockchain. Point it at your own node to keep your addresses private. |

For how to generate the TastyTrade variables, please refer to [this documentation](https://tastyworks-api.readthedocs.io/en/latest/sessions.html).
For how to generate the Interactive Brokers variables, please refer to
[Interactive Brokers Flex Queries and Caveats](#interactive-brokers-flex-queries-and-caveats).

If you don't wish to use all available providers when importing transactions,
simply don't provide the environment variables related to it.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Configuration File

Settings that don't fit in environment variables live in an optional YAML file,
`ghostcompanion.yaml` by default (see
[`ghostcompanion.example.yaml`](https://github.com/OliRafa/ghostcompanion/blob/main/ghostcompanion.example.yaml)):

```yaml
# Rename symbols before exporting to Ghostfolio: <source symbol>: <Ghostfolio symbol>.
symbol_mapping:
  EURN: CMBT

# Self-custody wallets, each tracked as its own Ghostfolio account.
wallets:
  - name: Cold Storage
    network: bitcoin
    addresses:         # every address the wallet uses, change addresses included
      - bc1q...
      - bc1q...
  - name: DeFi Wallet
    networks: [ethereum, base]   # one account for the same address on both
    addresses:
      - "0x..."

# Tokens EVM wallets track besides USDC and ETH (see "Ethereum and Base wallets").
tokens:
  cbBTC:                         # well known: no contract needed
    symbol: CBBTC
    data_source: GHOSTFOLIO
    price: BTC
  ABTC:                          # anything else: its network and contract
    network: base
    contract: "0x3764f07752384450576c6d8b027d06ffa29e5ae9"
    data_source: GHOSTFOLIO

# Binance's Transaction Records exports, relative to this file (see "Binance
# Exports and Caveats").
binance:
  history_path: binance
```

Wallet names must be unique and can't reuse an account name the importers create
(`Binance`, `Coinbase`, `Interactive Brokers`, `Tastytrade`), and an address can belong to a
single wallet. A wallet is either on `bitcoin` or on EVM networks (`ethereum`,
`base`). See [Self-Custody Wallets](#self-custody-wallets).

In the container the file is read from `/app/ghostcompanion.yaml`, so mount it
there (e.g. `-v ./ghostcompanion.yaml:/app/ghostcompanion.yaml:ro`).

> **Upgrading from `symbol_mapping.yaml`:** that file is no longer read. Move its
> entries under the `symbol_mapping` key of `ghostcompanion.yaml`; GhostCompanion
> refuses to start while only the old file is present.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Self-Hosted Ghostfolio Currencies

Activities keep the currency they were paid in (e.g. Coinbase buys paid in EUR),
and Ghostfolio converts them using its own exchange rates. A self-hosted instance
only gathers rates for the currencies of its accounts and asset profiles, not of
activities, so an activity in any other currency is valued at 0, which breaks
investment, average price and performance. Add each of those currencies (as an
admin) under **Admin Control → Market Data → Add Asset Profile → Add Currency**,
which also gathers its exchange rates. The [Ghostfolio cloud](https://ghostfol.io)
already has them.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Docker

For evaluation, you can run it by:

```sh
docker run --rm --name ghostcompanion \
-e GHOSTFOLIO_ACCOUNT_TOKEN=<account_token> \
-e TASTYTRADE_CLIENT_SECRET=my_client_secret \
-e TASTYTRADE_REFRESH_TOKEN=super_secure_token \
olirafa/ghostcompanion
```

It'll spawn the container, ingest all data from Tastytrade,
export it all to Ghostfolio, and then remove the container at the end.

To unleash the plugin's potential, you would want to deploy it scheduled
to run from time to time (weekly, for example).
For that, two approaches are presented, deploying using
[Docker Compose](#docker-compose) or in your
[Kubernetes](#kubernetes) cluster.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Docker Compose

The plugin was developed without a scheduler (like Cron) by design,
so another tool is needed for that.
We suggest using [Ofelia](https://github.com/mcuadros/ofelia),
and that's what we have in the provided
[Docker Compose file](https://github.com/OliRafa/ghostcompanion/blob/main/docker-compose.yml).

First, clone the repo:

```sh
git clone https://github.com/OliRafa/ghostcompanion.git
```

Enter the repo folder:

```sh
cd ghostcompanion
```

Then, you'll need a `.env` file with the
[environment variables](#environment-variables) set.
A example file can be found [here](https://github.com/OliRafa/ghostcompanion/blob/main/.env.example).

With everything ready, run the following command:

```sh
docker compose up -d
```

It will deploy it in your Docker Compose infrastructure, running weekly by default.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Kubernetes

Start by deploying [environment variables](#environment-variables) as
[ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap) and/or
[Secrets](https://kubernetes.io/docs/concepts/configuration/secret).

Since Kubernetes has a build-in scheduler, you can create a CronJob following
[the official documentation](https://kubernetes.io/docs/tasks/job/automated-tasks-with-cron-jobs).

For an example of such CronJob deployment, take a look below:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ghostcompanion
  namespace: ghostfolio
spec:
  schedule: "@hourly"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: ghostcompanion
              image: olirafa/ghostcompanion
              imagePullPolicy: IfNotPresent
              env:
                - name: GHOSTFOLIO_ACCOUNT_TOKEN
                  valueFrom:
                    configMapKeyRef:
                      name: ghostcompanion-configs
                      key: GHOSTFOLIO_ACCOUNT_TOKEN
                - name: GHOSTFOLIO_BASE_URL
                  valueFrom:
                    configMapKeyRef:
                      name: ghostcompanion-configs
                      key: GHOSTFOLIO_BASE_URL
                - name: TASTYTRADE_CLIENT_SECRET
                  valueFrom:
                    secretKeyRef:
                      name: tastytrade-credentials
                      key: client_secret
                - name: TASTYTRADE_REFRESH_TOKEN 
                  valueFrom:
                    secretKeyRef:
                      name: tastytrade-credentials
                      key: refresh_token
          restartPolicy: OnFailure
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Self-Custody Wallets

Each wallet in the [configuration file](#configuration-file) becomes a Ghostfolio
account with the wallet's name, filled from its confirmed on-chain transactions
(read from [mempool.space](https://mempool.space) or `MEMPOOL_BASE_URL`):

* **Every move is priced at market**, the way Coinbase itself accounts for coins
  moving in and out: coins leaving an account are sold, coins arriving are
  bought. For Coinbase sends and receives that's Coinbase's own value of the
  transaction; for wallets, the coin's price at the moment of the transaction
  ([DefiLlama](https://defillama.com), in USD), or that day's closing price on
  Yahoo Finance when DefiLlama has none, with a warning in the log.
* **Transfers between your own accounts** (e.g. Coinbase withdrawals to the
  wallet, or the other way around) are recognized by their transaction id. The
  source sells the coins and the destination buys them at the same price, from
  when they were sent, so the destination's cost is the coins' value when they
  arrived. Coinbase withdrawals to a wallet show up once the transaction
  confirms.
* **Network fees** paid by the wallet are sold for nothing, as Coinbase's are.

List every address the wallet uses, change addresses included: coins sent to an
address that isn't listed count as sold, so a payment's change sent to an
unlisted address looks like coins leaving the wallet, and a Coinbase withdrawal
to an unlisted wallet of yours books a sale instead of a transfer. When a
transaction spends listed and unlisted addresses together, GhostCompanion logs a
warning naming the unlisted ones.

What to expect in Ghostfolio:

* A transfer realizes a gain or loss on the sending account: Ghostfolio compares
  the sale's market price with that account's average buy price, as the Coinbase
  app does for withdrawals.
* The receiving wallet starts from the coins' value on arrival, so its
  performance counts what happened after the transfer.
* Ghostfolio has no notion of transfers, so a holding's combined figures across
  accounts (investment, average price) don't add up to the per-account ones.

> **Privacy:** a public block explorer sees every address it's asked about, all
> at once and from your IP, which links them to each other and to you. Pointing
> `MEMPOOL_BASE_URL` at your own [mempool](https://github.com/mempool/mempool) or
> [electrs](https://github.com/Blockstream/electrs) instance avoids that. The
> same goes for Alchemy and the addresses of EVM wallets.

### Ethereum and Base wallets

EVM wallets are read through [Alchemy](https://www.alchemy.com)
(`ALCHEMY_API_KEY`), on every network the wallet lists:

* **Tokens are recognized by their contract only.** Names and symbols are free
  text, which address-poisoning scams exploit: lookalike tokens (`USDꓚ`,
  `ÚSDС`), transfers spoofed in the wallet's name and zero-value transfers are
  all ignored. USDC and each network's own coin (ETH) are tracked out of the
  box; add others under `tokens`. A well-known one (`cbBTC`) needs no contract;
  any other needs its `network` and `contract`.
* **Each token says how Ghostfolio knows it:** its `symbol`, its `data_source`
  (`YAHOO` by default, which names coins as `<SYMBOL>USD` pairs) and, for moves
  that aren't swaps, the Yahoo coin pricing them when DefiLlama has no price for
  the token itself at that moment (`price`; e.g. `BTC` for cbBTC). A token
  without a `price` is only booked when a swap tells what it cost.
* **Swaps** (one coin given for another in a single transaction) sell the coin
  given and buy the one got at the price the swap actually got. That also prices
  coins with no market quote of their own, such as vault shares.
* **Network fees** are sold for nothing in ETH, including Base's L1 data fee, for
  every transaction the wallet signed; a failed one only costs its fee.
* **Aave** (v3's core market, on every network the wallet lists): what the
  wallet supplies or owes stays in the wallet's own account, as it does on the
  chain, and every activity Aave is behind names it:
  * Supplying and withdrawing book nothing: the coin is still the wallet's.
  * Borrowing buys the coin and sells a `DEBT-<SYMBOL>` holding (e.g.
    `DEBT-USDC`), both "Borrowed from Aave", so the debt shows as a negative
    holding valued at the coin's price. Repaying sells the coin and buys the
    debt back ("Repaid to Aave"). Aave rounds a new debt up by a unit of the
    coin: that unit is sold for nothing on its own ("Rounded up by Aave"), so a
    debt repaid in full ends at exactly zero.
  * A debt is bought back for nothing, with what repaid it as a fee. Ghostfolio
    measures a sale against the average of the buys since the holding was last
    at zero, so buying a debt back at its price would turn every later borrow
    into a loss of that price. Net performance then counts debts right, overall
    and per holding, but Ghostfolio's fees and gross performance include what
    was repaid.
  * What's done without the wallet's own coins, such as a collateral swap or
    repaying with collateral through a relayer (CoW Protocol, Aave's adapters),
    is read from Aave's own events whoever signed it, and booked as a swap "on
    Aave": one supplied coin for another, or collateral for debt.
  * Interest moves no coin. Aave adds it to a position every time it touches
    it, so it's booked then, a second before that move so Ghostfolio always
    counts it first: interest earned is bought for nothing ("Interest earned on
    Aave") and interest due is sold for nothing ("Interest due to Aave"). Every
    import also compares what Aave holds for the wallet with what was booked
    there, and books the interest accrued since Aave's last move, dated the day
    of the import.
  * A gap interest can't explain (a position that shrank, or grew more than
    25% a year since its last move) means a move went unread. It's still
    booked, so holdings match Aave, but as a "Balance correction on Aave", with
    a warning in the log.
  * Other protocols aren't modelled yet: coins lent to or borrowed from them
    count as sent and received.

Tokens with a data source other than `YAHOO` need Ghostfolio to price them, e.g.
through a price proxy behind its `GHOSTFOLIO` data source (`PROXY_ROUTES` and
`API_KEY_GHOSTFOLIO` admin settings), with the same symbols. Debts are always
booked under `GHOSTFOLIO`, so borrowing needs one too, serving `DEBT-<SYMBOL>`
at the price of the coin owed (e.g. `DEBT-USDC` from Yahoo's `USDC-USD`).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Binance Exports and Caveats

Binance is read from two places:

* **Its API** (`BINANCE_API_KEY` and `BINANCE_SECRET`, created under
  **Account → API Management** with only **Enable Reading** on): balances, every
  crypto deposit and withdrawal, with the transaction ids that pair them with
  Coinbase and your wallets, and trades.
* **Transaction Records exports**, for older trades. Since November 2024
  Binance's API returns no trades from before September 2022
  ([CoinTracking](https://cointracking.freshdesk.com/en/support/solutions/articles/29000039887-binance-import-restrictions)
  documents the cutoff), and a Tax Report API key reaches no further.

To export them, on the Binance website (not the app):

1. Hover the wallet icon in the header and choose **Asset History**.
2. Hover the download icon at the top right and choose **Export Transaction
   Records**.
3. Keep **Data Type** on `Asset History – Transaction History`, **Coin** and
   **Account** on `All`, set **Time Range** to `Customize` from your first
   activity to today, and pick **CSV**.
4. Click **Generate**. Once Binance tells you it's ready, open the same pop-up
   and **Download** it.
5. Put the file, untouched, in the folder `binance.history_path` names: opening
   and saving it in a spreadsheet changes its dates and numbers. If Binance
   limits how long one export covers, export each period into a file of its
   own; periods mustn't overlap.

In the container, mount that folder next to the config file (e.g.
`-v ./binance:/app/binance:ro` with `history_path: binance`).

How Binance is booked, in its own `Binance` account:

* **Trades against fiat** (BRL, EUR…) are buys and sells in that fiat, with a
  fee in it as the trade's fee.
* **A coin traded for another**, stablecoins included, is a swap, valued at
  BTC's or ETH's price at the moment when one of them is a side, or else at the
  coin given's daily close.
* **A fee paid in a coin** (BNB, or the coin bought) is that coin sold for
  nothing, a second after the trade.
* **Airdrops** are bought for nothing, and **a coin Binance renamed** (NANO to
  XNO) is booked under its new name throughout.
* **Deposits and withdrawals** come from the API and are booked like Coinbase's
  sends and receives, transfers to and from your other accounts included (see
  [Self-Custody Wallets](#self-custody-wallets)).

Trades made after the exports end come from the API. Finding them means asking
about every pair a coin could have been traded in, which takes minutes, so it's
only done when today's balances differ from what the exports and the API's
deposits and withdrawals since add up to. Whatever still doesn't add up is
logged as a warning naming the coin and the difference: the importer doesn't
read Earn, Convert or dust conversions from the API, nor margin, futures, P2P
or card buys. Export records it doesn't book are warned about the same way.

Fiat left on Binance becomes the account's cash balance only in the account's
currency (USD unless you change it in Ghostfolio). On a self-hosted Ghostfolio,
add the fiat you traded in as described in
[Self-Hosted Ghostfolio Currencies](#self-hosted-ghostfolio-currencies).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Interactive Brokers Flex Queries and Caveats

Current implementation for getting Interactive Brokers transactions
relies on Flex Queries.

To generate the Flex Query, please refer to
[the official documentation](https://www.ibkrguides.com/orgportal/performanceandstatements/flex.htm).

At minimum, you'll need the following configurations:

* Select `Change in Dividend Accruals`
  * Mark all checkboxes
* Select `Trades`
  * Select `Execution`
  * Mark all checkboxes
* Select Format `XML`
* Select Date Format `yyyyMMdd`
* Select Time Format `HHmmss`
* Select Date/Time Separator `; (semi-colon)`
* Select `Include Canceled Trades`

On `Period` comes the caveat.
Flex Queries only allows for a maximum period of `Last 365 Calendar Days`,
which means that any transaction prior to that date won't be listed in the
Flex Query, and hence it won't be automatically inserted into Ghostfolio.

This means that any transaction prior to that date should be added manually
in Ghostfolio, and GhostCompanion won't change those when updating the account
with new transactions.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

* [-] Binance
  * [x] Spot trades (from Transaction Records exports, and the API after them)
  * [x] Trading fees
  * [x] Deposits and withdrawals, transfers with your other accounts included
  * [x] Airdrops and coin renames
  * [x] Account balance
  * [ ] Convert, Earn and dust conversions after the exports
* [-] Coinbase
  * [x] Crypto buys and sells
  * [x] Crypto transaction fees
  * [x] Transfers to and from self-custody wallets
  * [ ] Account balance
* [-] Self-custody wallets
  * [x] Bitcoin
  * [x] Ethereum and Base (USDC, ETH and configured tokens, swaps included)
  * [ ] DeFi positions (lending, borrowing)
* [-] Interactive Brokers
  * [x] Stock buys and sells
  * [ ] Forward share splits
  * [ ] Symbol changes
  * [x] Dividends and dividend reinvestments
  * [ ] Account balance
* [-] TastyTrade
  * [x] Stock buys and sells
  * [x] Forward share splits
  * [x] Symbol changes
  * [x] Dividends and dividend reinvestments
  * [x] Account balance

See the [open issues](https://github.com/OliRafa/ghostcompanion/issues)
for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Contributions are what make the open source community such an
amazing place to learn, inspire, and create.
Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better,
please fork the repo and create a pull request.
You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Enable the git hooks once: `./scripts/setup-hooks.sh`
4. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
5. Push to the Branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

### Continuous Integration

CI is a single script, `scripts/ci.sh`, that runs formatting (Black), import
sorting (isort), linting (pylama), and the test suite. The exact same script
runs as the `pre-commit` and `pre-push` git hooks and on GitHub Actions, so
whatever passes locally passes CI. Run `./scripts/setup-hooks.sh` once after
cloning to enable the hooks; run `./scripts/ci.sh` any time to reproduce CI.

### Local Ghostfolio

The e2e suite (and manual testing) needs a Ghostfolio instance. Spin one up
locally with:

```sh
docker compose -f docker-compose.dev.yml up -d --wait
```

Then set `GHOSTFOLIO_BASE_URL=http://localhost:3333` in your `.env`. Without a
`GHOSTFOLIO_ACCOUNT_TOKEN` the e2e suite creates a throwaway user and deletes it
at the end; with one, that user's accounts and activities are wiped before and
after the run. To get a token for manual testing, create a user with
`curl -X POST http://localhost:3333/api/v1/user` and use the returned
`accessToken` (the first user created is the instance admin). If your
activities use other currencies than USD, add them as described in
[Self-Hosted Ghostfolio Currencies](#self-hosted-ghostfolio-currencies).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors

<a href="https://github.com/OliRafa/ghostcompanion/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OliRafa/ghostcompanion"
    alt="contrib.rocks image" />
</a>

## Acknowledgments

* [Ghostfolio](https://github.com/ghostfolio/ghostfolio) for being an amazing tool!
* [Interactive Brokers (IBKR)](https://www.interactivebrokers.com) for the API and
[agusalex/ibflex](https://github.com/agusalex/ibflex)
for the API Python wrapper.
* [Tastytrade](https://tastytrade.com) for the API and
[tastyware/tastytrade](https://github.com/tastyware/tastytrade)
for the API Python wrapper.
* [mempool.space](https://mempool.space) for the blockchain API.
* [Alchemy](https://www.alchemy.com) for the EVM chain data API.
* [DefiLlama](https://defillama.com) for the coin prices API.
* [Yahoo Finance](https://finance.yahoo.com) for the API and
[ranaroussi/yfinance](https://github.com/ranaroussi/yfinance)
for the API Python wrapper.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the Unlicense License.
See `[LICENSE.txt](https://github.com/OliRafa/ghostcompanion/blob/main/LICENSE)`
for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

> Rafael Oliveira &nbsp;&middot;&nbsp;
> [olirafa.github.io](https://olirafa.github.io) &nbsp;&middot;&nbsp;
> GitHub [@OliRafa](https://github.com/OliRafa) &nbsp;&middot;&nbsp;
> LinkedIn [@OliRafa](https://www.linkedin.com/in/OliRafa)

<!-- MARKDOWN LINKS & IMAGES -->
[buy-me-a-coffee-shield]: https://img.shields.io/badge/buy_me_a_coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[buy-me-a-coffee-url]: https://buymeacoffee.com/olirafaa
[github-sponsors-shield]: https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&style=for-the-badge
[github-sponsors-url]: https://github.com/sponsors/OliRafa
[poetry-shield]: https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json&style=for-the-badge
[poetry-url]: https://python-poetry.org
[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[python-url]: https://www.python.org
