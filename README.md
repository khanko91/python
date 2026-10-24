# LG TV debloat + Material home screen

Tools for cleaning up an LG webOS TV and giving it a Material 3 (Google Material Design) start screen.

| What                          | Stock TV | Rooted TV (Homebrew Channel) |
|-------------------------------|:--------:|:----------------------------:|
| Turn off ads & recommendations (Settings) | yes | yes |
| List all apps (`debloat.py apps`)         | yes | yes |
| Install the Material launcher             | yes, via Developer Mode | yes |
| Uninstall preinstalled apps (`remove`)    | no  | user-partition apps only |
| Open the launcher automatically at boot (`autostart`) | no | yes |

webOS doesn't let you replace the built-in Home launcher. The Home button still opens LG's bar. The Material launcher is a normal app that you pin first, or that opens automatically at boot on a rooted TV.

## 1. Turn off ads (any TV, do this first)

Menu names vary slightly by webOS version:

- **Settings → General → System → Additional Settings → Home Settings**: turn off *Home Promotion*, *Content Recommendation* and *Auto-launch Home*.
- **Settings → General → System → Additional Settings → Advertisement**: turn on *Limit Ad Tracking*. Turn off *Live Plus* (it recognizes what's on screen).
- **Settings → Support → Privacy & Terms → User Agreements**: decline *Viewing Information* and *Interest-Based Advertising*.
- On the Home bar, long-press OK on unwanted tiles and choose **Remove** or **Hide**.

## 2. List your apps

```sh
pip install -r requirements.txt
python -m lgtv.debloat --host 192.168.1.50 apps
```

Accept the pairing prompt on the TV the first time. The key is saved to `~/.lgtv_client_key`.

## 3. Remove apps (rooted TVs only)

Root requires the [Homebrew Channel](https://github.com/webosbrew/webos-homebrew-channel) and a firmware vulnerable to a current root method (see [CanI.RootMy.TV](https://cani.rootmy.tv)). Enable SSH in Homebrew Channel settings and add your SSH key.

Rooting carries risk and may void your warranty.

```sh
# edit lgtv/bloat.txt to match the ids from step 2, then:
python -m lgtv.debloat --host 192.168.1.50 remove --file lgtv/bloat.txt        # dry run
python -m lgtv.debloat --host 192.168.1.50 remove --file lgtv/bloat.txt --yes  # do it
```

- Home, Settings, Live TV, inputs, the LG Content Store and Homebrew Channel are protected and always skipped.
- Apps baked into the firmware partition are read-only. Removing them will report `failed`. Hide them from the Home bar instead.

## 4. Install the Material launcher

`lgtv/launcher/` is a webOS web app. It shows a clock, a greeting, an app row and an input row, and works with the remote's arrow keys and OK button.

With the [webOS CLI](https://webostv.developer.lge.com/develop/tools/cli-installation) and either Developer Mode or a rooted TV:

```sh
ares-package lgtv/launcher -o dist
ares-install -d mytv dist/com.material.launcher_1.0.0_all.ipk
```

- On a rooted TV, the launcher reads your real installed apps.
- On a Developer Mode TV, it may not have permission to list apps and will show the shortcuts in `FALLBACK_APPS` in `index.html` instead. Edit that list to suit you.
- Developer Mode apps expire unless you renew the session. Homebrew Channel installs don't expire.

To open it automatically on boot (rooted TVs):

```sh
python -m lgtv.debloat --host 192.168.1.50 autostart            # enable
python -m lgtv.debloat --host 192.168.1.50 autostart --disable  # undo
```

## Tests

```sh
python -m pytest
```
