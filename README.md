<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Python][python-shield]][python-url]
[![Poetry][poetry-shield]][poetry-url]
[![Buy Me A Coffee][buy-me-a-coffee-shield]][buy-me-a-coffee-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
<h3 align="center">Tastytrade-Ghostfolio</h3>

  <p align="center">
    Transfer <a href="https://tastytrade.com" target="_blank">Tastytrade</a> transactions to <a href="https://github.com/ghostfolio/ghostfolio" target="_blank">Ghostfolio</a>.
    <br />
    <br />
    <p align="center">
      <a href="#getting-started">Getting Started</a> •
      <a href="#credits">Credits</a> •
      <a href="https://github.com/OliRafa/tastytrade-ghostfolio/issues/new?labels=bug&template=bug-report---.md">Report Bug</a> •
      <a href="https://github.com/OliRafa/tastytrade-ghostfolio/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a> •
      <a href="#roadmap">Roadmap</a>
    </p>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#environment-variables">Environment Variables</a></li>
        <li><a href="#docker">Docker</a></li>
        <li><a href="#docker-compose">Run with Docker Compose</a></li>
        <li><a href="#kubernetes">Kubernetes</a></li>
      </ul>
    </li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>


<!-- GETTING STARTED -->
## Getting Started

Tastytrade-Ghostfolio plugin works best when doing account management all by itself.
In other words, manually creating activities in your Ghostfolio account is not only not needed, but it's also discouraged.
That's because some operations (like symbol change, or stock splits) need to understand the complete picture of the account, and change its state
totally.

It'll start by getting (or creatting) a `Tastytrade` account from Ghostfolio, and from that it'll start adding trading transactions and/or dividends.

This plugin runs completely in the background, and is provided as container images hosted on
<a href="https://hub.docker.com/r/olirafa/tastytrade-ghostfolio" target="_blank">Docker Hub</a> for `linux/amd64`.



### Environment Variables

Start by setting up the appropriate environment variables, listed below:

| Name                       | Type                | Default Value         | Description                                                                                                                                                             |
| -------------------------- | ------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GHOSTFOLIO_ACCOUNT_TOKEN` | `string`            |                       | The _Ghostfolio_ Account Token.                                                                                                                                         |
| `GHOSTFOLIO_BASE_URL`      | `string` (optional) | "https://ghostfol.io" | The _Ghostfolio_ URL. If you're self hosting you should change it for your particular instance URL, otherwise all data will be exported to _Ghostfolio_ cloud offering. |
| `TASTYTRADE_USERNAME`      | `string`            |                       | The _Tastytrade_ username.                                                                                                                                              |
| `TASTYTRADE_PASSWORD`      | `string`            |                       | The _Tastytrade_ password.                                                                                                                                              |


### Docker

For evaluation, you can run it by:

```sh
$ docker run --rm --name tastytrade-ghostfolio -e GHOSTFOLIO_ACCOUNT_TOKEN=<account_token> -e TASTYTRADE_USERNAME=myuser -e TASTYTRADE_PASSWORD=super_secure olirafa/tastytrade-ghostfolio
```

It'll spawn the container, ingest all data from Tastytrade, export it all to Ghostfolio, and then remove the container at the end.

To unleash the plugin's potential, you would want to deploy it scheduled to run from time to time (weekly, for example).
For that, two approaches are presented, deploying using <a href="#docker-compose">Docker Compose</a> or in your
<a href="#kubernetes">Kubernetes</a> cluster.

### Docker Compose

The plugin was developed without a scheduler (like Cron) by design, so another tool is needed for that.
We suggest using <a href="https://github.com/mcuadros/ofelia" target="_blank">Ofelia</a>, and that's what we have in the provided
<a href="https://github.com/OliRafa/tastytrade-ghostfolio/blob/main/docker-compose.yml" target="_blank">Docker Compose file</a>.

First, clone the repo:
```sh
$ git clone https://github.com/OliRafa/tastytrade-ghostfolio.git
```

Enter the repo folder:
```sh
$ cd tastytrade-ghostfolio
```

Then, you'll need a `.env` file with the <a href="#environment-variables">environment variables</a> set.
A example file can be found <a href="https://github.com/OliRafa/tastytrade-ghostfolio/blob/main/.env.example" target="_blank">here</a>.

With everything ready, run the following command:
```sh
$ docker compose up -d
```

It will deploy it in your Docker Compose infrastructure, running weekly by default.

### Kubernetes

Start by deploying <a href="#environment-variables">environment variables</a> as
<a href="https://kubernetes.io/docs/concepts/configuration/configmap" target="_blank">ConfigMaps</a> and/or
<a href="https://kubernetes.io/docs/concepts/configuration/secret" target="_blank">Secrets</a>.

Since Kubernetes has a build-in scheduler, you can create a CronJob following
<a href="https://kubernetes.io/docs/tasks/job/automated-tasks-with-cron-jobs" target="_blank">the official documentation</a>.

For an example of such CronJob deployment, take a look below:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: tastytrade-ghostfolio
  namespace: ghostfolio
spec:
  schedule: "@hourly"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: tastytrade-ghostfolio
              image: olirafa/tastytrade-ghostfolio
              imagePullPolicy: IfNotPresent
              env:
                - name: GHOSTFOLIO_ACCOUNT_TOKEN
                  valueFrom:
                    configMapKeyRef:
                      name: tastytrade-ghostfolio-configs
                      key: GHOSTFOLIO_ACCOUNT_TOKEN
                - name: GHOSTFOLIO_BASE_URL
                  valueFrom:
                    configMapKeyRef:
                      name: tastytrade-ghostfolio-configs
                      key: GHOSTFOLIO_BASE_URL
                - name: TASTYTRADE_USERNAME
                  valueFrom:
                    secretKeyRef:
                      name: tastytrade-credentials
                      key: user
                - name: TASTYTRADE_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: tastytrade-credentials
                      key: password
          restartPolicy: OnFailure
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- ROADMAP -->
## Roadmap

- [x] Stock buys and sells
- [x] Forward share splits
- [x] Symbol changes
- [x] Dividends and dividend reinvestments
- [ ] Account balance

See the [open issues](https://github.com/OliRafa/tastytrade-ghostfolio/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/OliRafa/tastytrade-ghostfolio/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OliRafa/tastytrade-ghostfolio" alt="contrib.rocks image" />
</a>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* <a href="https://github.com/ghostfolio/ghostfolio" target="_blank">Ghostfolio</a> for being an amazing tool!
* <a href="https://tastytrade.com" target="_blank">Tastytrade</a> for the API and
<a href="https://github.com/tastyware/tastytrade" target="_blank">tastyware/tastytrade</a> for the API Python wrapper.
* <a href="https://finance.yahoo.com/" target="_blank">Yahoo Finance</a> for the API and
<a href="https://github.com/ranaroussi/yfinance" target="_blank">ranaroussi/yfinance</a> for the API Python wrapper.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the Unlicense License.
See <a href="https://github.com/OliRafa/tastytrade-ghostfolio/blob/main/LICENSE" target="_blank">`LICENSE.txt`</a> for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


---

> Rafael Oliveira &nbsp;&middot;&nbsp;
> [olirafa.github.io](https://olirafa.github.io) &nbsp;&middot;&nbsp;
> GitHub [@OliRafa](https://github.com/OliRafa) &nbsp;&middot;&nbsp;
> LinkedIn [@OliRafa](https://www.linkedin.com/in/OliRafa)




<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[buy-me-a-coffee-shield]: https://img.shields.io/badge/buy_me_a_coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[buy-me-a-coffee-url]: https://buymeacoffee.com/olirafaa
[poetry-shield]: https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json&style=for-the-badge
[poetry-url]: https://python-poetry.org
[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[python-url]: https://www.python.org