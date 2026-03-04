<p align="center">
  <img src="public/logo192.png" alt="App Logo" />
</p>

<div align="center">
  
[Live App](https://chat.positive-intentions.com) | [Docs](https://positive-intentions.com) | [Reddit](https://www.reddit.com/r/positive_intentions) | <a rel="me" href="https://infosec.exchange/@xoron">Mastodon</a>
</div>

<div align="center">
  
![GitHub stars](https://img.shields.io/github/stars/positive-intentions/chat?style=social) 
![GitHub forks](https://img.shields.io/github/forks/positive-intentions/chat?style=social) 
![GitHub issues](https://img.shields.io/github/issues/positive-intentions/chat) 
![GitHub license](https://img.shields.io/github/license/positive-intentions/chat) 
![Staging](https://github.com/positive-intentions/chat/actions/workflows/main_workflow.yaml/badge.svg) 
[![gh-pages-build-deployment](https://github.com/positive-intentions/chat/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/positive-intentions/chat/actions/workflows/pages/pages-build-deployment)
[![CodeQL](https://github.com/positive-intentions/chat/actions/workflows/codeql.yml/badge.svg)](https://github.com/positive-intentions/chat/actions/workflows/codeql.yml)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
</div>

# Chat

> ⚠️ **WARNING:** This project is not production-ready. It is an unstable experimental proof-of-concept and may contain bugs and/or incomplete features. Use it at your own risk.

A chat app designed to work within your browser, with a focus on browser-based security and decentralization.


<p align="center">
  <img width="50%" src="https://positive-intentions.com/assets/images/computers-b515cec053bf6448ec611a096c944e9c.png" alt="multi-platform Logo" />
</p>

**Feature-Rich Experience**:
- **Secure Messaging**: End-to-end encryption for all messages.
- **File Sharing**: Seamlessly share files with peers using cutting-edge WebRTC technology.
- **Voice and Video Calls**: Connect more personally with high-quality calls.
- **Mixed-Reality Spaces**: Dive into shared virtual environments for a new way of interaction.[VR preview](https://www.youtube.com/watch?v=2gTTu4OqoiM), [AR preview](https://www.youtube.com/shorts/8vYCwMg7T7E), [ML/TF preview](https://positive-intentions.com/assets/images/hand-pose-ef32ea87200e51c333629846287d20ea.gif)
- **Image Board**: Share and discover images in a community-driven space. [Gram preview](https://chat.positive-intentions.com/#/feed)
- **Webtop Environment**: Desktop experience on the browser. [Desk preview](https://chat.positive-intentions.com/#/desk)

<p align="center">
  <img width="50%" src="https://positive-intentions.com/assets/images/phones-7e2bee3441aae5ebb4da3d2671d8f568.png" alt="multi-platform Logo" />
</p>

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

## Trying it out

Try it out between you phone and laptop. The app is using browser storage, so if you open 2 tabs of the app, they will use and update the same data. This can lead to conflict issues and should be avoided. instead if you want to try on a single device, you can try between different browsers (like chrome and edge). Its also worth noting that incognito modes on all the browsers would also use a different store.

> Suggestions for troubleshooting
> - Its best to start off by clearing all site data from the browser settings.
> - Do not have multiple tabs of the app on the same device.
> - It doesnt hurt to refresh to page.

## Prerequisites for development

You need to have Node.js installed on your system to run the app. If you don't have Node.js installed, you can download it from [here](https://nodejs.org/).

### Running the app

First, clone the repository to your local machine.

For users that dont want to install anything and just want to try the app locally, you can open the file found at `<root>/Frontend/index.html` in a browser of your choice. 

#### For NPM users:

```bash
npm install
npm start
```

#### For docker users:

```bash
npm run docker:build # docker build -t chat -f docker/Chat.Dockerfile . --no-cache
npm run docker:run # docker run --name chat-container -p 8080:80 chat
```

This will start the development server and open the app in your default browser. If it doesn't open automatically, you can navigate to [http://localhost:8080](http://localhost:8080) to view the app.

> See the [package.json](package.json) file for more scripts.

#### For GitHub users:

You can fork the repo and host it on Github Pages for free if the repository is made public. After forking the repo, you can go to Settings>Pages to set the following:
- Source: "Deploy from a branch"
- Branch: "staging"
- Select folder: "/docs"

Finally click "Save" to enable Github Pages.

## iOS, Android and Desktop

<p align="center">
  <img width="50%" src="https://positive-intentions.com/assets/images/native-560076a3f27240fc0ea3b39da576637b.png" alt="multi-platform Logo" />
</p>

The app can be installed on iOS, Android and Desktop. The project is not mature enough to be published on the app stores ([exception](https://store.app/chat-staging-positive-intentions-com)?). This repository has the necessary files to build the app for these platforms. This should be done by someone with experience in building apps for these platforms.

### iOS and Android

To build for mobile, you need to have respective build tools installed on your computer (xcode/android studio) installed on your system. the build is created with capacitorjs found [here](https://capacitorjs.com/). See the folders `ios` and `android` in the root folder for the build files.

### Desktop

To build for desktop, you need to install the dependencies with the `npm i` command, then you may also need to install rust on your system as described [here](https://tauri.app/v1/guides/getting-started/prerequisites/). The desktop build is based on Tauri found [here](https://tauri.app/). You can create a build by running `npm run tauri build`. the build will be found in the `tauri/target/release/bundle` folder (you may need to add executable permissions `chmod +x <filename>`).

## Security and privacy recommendations

<p align="center">
  <img width="50%"src="https://positive-intentions.com/assets/images/lock-f89d113c69bad9225d302acbf8e3dbf5.png" alt="lock Logo" />
</p>

This project is aiming to create the most secure and private chat app. It will heavily depend on how you use it. Here are some reccomended security optimizations/advice to keep your data secure and private:

- Use a self-hosted instance of the app.
- Use a VPN to protect your data from being intercepted.
- Only connect to trusted peers.
- Validate public key hashes.
- You and your peer should use a secure device/os/browser with the latest updates.
- use general security practices like not sharing sensitive information, not clicking on suspicious links, etc.


## Join Us on This Journey

Pushing the boundaries of what's possible with current web technologies to create a chat app that prioritizes user empowerment and privacy. But this is just the beginning. With your support, we can explore new features, refine the user experience, and expand the app's capabilities.

### How You Can Help

- **Feedback**: Your insights are invaluable. Share your thoughts on current features, suggest new ones, or report any bugs you encounter.
- **Spread the Word**: Help us grow by sharing the app with others who value privacy and control over their digital communication.
- **Github Stars**: If you like the project, consider starring the repository. It helps others discover it and boosts our motivation.
- **Sponsorship**: Development is fueled by passion and coffee. Your sponsorship helps keep both flowing.

## Star History

<a href="https://star-history.com/#positive-intentions/chat&Timeline">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=positive-intentions/chat&type=Timeline&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=positive-intentions/chat&type=Timeline" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=positive-intentions/chat&type=Timeline" />
 </picture>
</a>

