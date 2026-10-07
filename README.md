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

Currently implemented for [Coinbase](https://coinbase.com),
[Interactive Brokers (IBKR)](https://www.interactivebrokers.com), [Tastytrade](https://tastytrade.com)
and self-custody Bitcoin wallets.
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
(`Coinbase`, `Interactive Brokers`, `Tastytrade`, or each
[self-custody wallet](#self-custody-wallets) by its name) from Ghostfolio,
and from that it'll start adding trading transactions and/or dividends.

This plugin runs completely in the background, and is provided as
container images hosted on
[Docker Hub](https://hub.docker.com/r/olirafa/ghostcompanion) for `linux/amd64`.

### Environment Variables

Start by setting up the appropriate environment variables, listed below.

| Name                       | Type                | Default Value         | Description                                                                                                                                                             |
| -------------------------- | ------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
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
    network: bitcoin   # the only network supported so far
    addresses:         # every address the wallet uses, change addresses included
      - bc1q...
      - bc1q...
```

Wallet names must be unique and can't reuse a broker account name
(`Coinbase`, `Interactive Brokers`, `Tastytrade`), and an address can belong to a
single wallet. See [Self-Custody Wallets](#self-custody-wallets).

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
  transaction; for wallets, that day's closing price (Yahoo Finance, in USD).
* **Transfers between your own accounts** (e.g. Coinbase withdrawals to the
  wallet, or the other way around) are recognized by their transaction id. The
  source sells the coins and the destination buys them at the same price, on the
  day they were sent, so the destination's cost is the coins' value when they
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
> [electrs](https://github.com/Blockstream/electrs) instance avoids that.

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

* [-] Coinbase
  * [x] Crypto buys and sells
  * [x] Crypto transaction fees
  * [x] Transfers to and from self-custody wallets
  * [ ] Account balance
* [-] Self-custody wallets
  * [x] Bitcoin
  * [ ] Other networks
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
