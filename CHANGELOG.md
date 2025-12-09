# Changelog

All notable changes to this project will be documented in this file.

## [2.0.1](https://github.com/OliRafa/ghostcompanion/compare/v2.0.0...v2.0.1) (2025-12-09)


### Bug Fixes

* **account:** managed message stating old library name ([f746d56](https://github.com/OliRafa/ghostcompanion/commit/f746d566aade46534e90752c2c8809eed818fb11))
* **tastytrade:** not being able to login due to login method deprecation ([f695e79](https://github.com/OliRafa/ghostcompanion/commit/f695e790140d764fdd6402d118d0730175910c13))

# [2.0.0](https://github.com/OliRafa/ghostcompanion/compare/v1.5.2...v2.0.0) (2025-08-04)


### Code Refactoring

* rename project to ghostcompanion ([51f139a](https://github.com/OliRafa/ghostcompanion/commit/51f139aaa756e9f6234c88ba267a9c2649e23740))


### BREAKING CHANGES

* close #15.

## [1.5.2](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.5.1...v1.5.2) (2025-05-09)


### Bug Fixes

* **readme:** change buy me a coffee url ([42132c4](https://github.com/OliRafa/tastytrade-ghostfolio/commit/42132c496e9cdecfe2eb9dee73bcb30c08754fe8))

## [1.5.1](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.5.0...v1.5.1) (2025-05-08)


### Bug Fixes

* fix yfinance rate limit / too many requests ([e395b62](https://github.com/OliRafa/tastytrade-ghostfolio/commit/e395b62046592c185c90669efae03834d1f06469))

# [1.5.0](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.4.3...v1.5.0) (2025-01-28)


### Features

* **dividends:** add dividends and dividend reinvestments calculations ([113789a](https://github.com/OliRafa/tastytrade-ghostfolio/commit/113789aa7208e2372fa7e659c1d5305cc5ecfdb7))

## [1.4.3](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.4.2...v1.4.3) (2025-01-16)


### Bug Fixes

* fix tastytrade changing their api ([2be150e](https://github.com/OliRafa/tastytrade-ghostfolio/commit/2be150edee7487364008e7046721bbd6a1eb42a9))

## [1.4.2](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.4.1...v1.4.2) (2024-12-23)


### Bug Fixes

* **forward-split:** fix unit price after split not being calculated properly ([6d59c38](https://github.com/OliRafa/tastytrade-ghostfolio/commit/6d59c38931ca77c0732f5e448420838196433567))

## [1.4.1](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.4.0...v1.4.1) (2024-12-23)


### Bug Fixes

* fix outdated orders not being handled properly ([9f39e84](https://github.com/OliRafa/tastytrade-ghostfolio/commit/9f39e846d2de6be625ad53895bb33cbb461d31d9))

# [1.4.0](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.3.1...v1.4.0) (2024-12-23)


### Features

* handle forward share splits ([06e32d6](https://github.com/OliRafa/tastytrade-ghostfolio/commit/06e32d617744c471600026319e45767b3fa04efd)), closes [#11](https://github.com/OliRafa/tastytrade-ghostfolio/issues/11)

## [1.3.1](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.3.0...v1.3.1) (2024-12-23)


### Bug Fixes

* fix reinserting sell orders multiple times ([3fdda8c](https://github.com/OliRafa/tastytrade-ghostfolio/commit/3fdda8c799f4aa8b71a0659372c727e4a6b1d576))

# [1.3.0](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.2.0...v1.3.0) (2024-12-20)


### Features

* automatically adapt symbol changes ([5f32ab4](https://github.com/OliRafa/tastytrade-ghostfolio/commit/5f32ab46561b05048e7076748366507ddff326f5))

# [1.2.0](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.1.0...v1.2.0) (2024-12-20)


### Features

* **ghostfolio-export:** adapt symbols from mapping file for ghostfolio/yahoo ([5a2c82b](https://github.com/OliRafa/tastytrade-ghostfolio/commit/5a2c82bf97cd6f2e95b7d51b7c545c84863b3aca))

# [1.1.0](https://github.com/OliRafa/tastytrade-ghostfolio/compare/v1.0.0...v1.1.0) (2024-12-19)


### Features

* **trade-types:** add support for sell ([b578239](https://github.com/OliRafa/tastytrade-ghostfolio/commit/b578239ddf5009f4c72cdc7c735d2ca627d88c0f))

# 1.0.0 (2024-03-24)


### Bug Fixes

* fix activities not being added to the correct account id ([ecd956b](https://github.com/OliRafa/tastytrade-ghostfolio/commit/ecd956b1d2a8efa5c989a45ba636bbc793879ca1))


### Features

* **accounts:** add behaviour to get or create the account in ghostfolio ([51a04c7](https://github.com/OliRafa/tastytrade-ghostfolio/commit/51a04c75cba12ba665a436b4ae3fe6377262da20)), closes [#3](https://github.com/OliRafa/tastytrade-ghostfolio/issues/3)
* add filter for already inserted activities ([460884d](https://github.com/OliRafa/tastytrade-ghostfolio/commit/460884d37fbe9037b3437a2822a9af7c41b84bf0)), closes [#4](https://github.com/OliRafa/tastytrade-ghostfolio/issues/4)
* add ghostfolio activities pushing mechanism ([35c6b64](https://github.com/OliRafa/tastytrade-ghostfolio/commit/35c6b64151c2db68f595ab356eecd2092fd85110)), closes [#2](https://github.com/OliRafa/tastytrade-ghostfolio/issues/2)
* **tastytrade:** add behaviour to import buy transactions ([3406aa5](https://github.com/OliRafa/tastytrade-ghostfolio/commit/3406aa5f1ab5d193846b6472a908a2ffc0ae107c)), closes [#1](https://github.com/OliRafa/tastytrade-ghostfolio/issues/1)
