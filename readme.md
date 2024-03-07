# Tinder Automatisator
This is a wrapper module based on a fork of [TinderBotz](https://github.com/frederikme/TinderBotz).

Intended functionality is to support two modes:
* __training__ - the user can swipe profiles while the script will record their decision;
* __autonomous__ - where the script makes swiping decision based on the user's preferences learned during _training_;

#### Changes to TinderBotz
The script uses [TinderBotz fork](https://github.com/iteriter/TinderBotz) which was updated slightly to work with the latest Tinder html layout.

### Instructions
0. poetry is used for dependency management; Install it [here](https://python-poetry.org/);
1. clone and cd to this repository;
2. run `poetry install` to install dependencies;
3. enter `poetry shell`, then run `python3 tinder_auto.py [mode] [auth_type]`, where [mode] is _training_ or _auto_, and [auth_type] is _phone_, _google_ or _facebook_;
    - for any auth type credentials should be supplied on the first line of the auth.txt, separeted by semicolon, e.g. `email:password` or `country:phone`;
4. wait for the browser to launch and login to Tinder. allow location and close the rest of the popups;
5. wait until the script outputs "You can swipe now" and swipe using _Left arrow_ or _Right arrow_ key. wait until script finished recording profile and lets you know to swipe again;
6. script will exit after a set timout if no action is taken;

### Limitations
* auto mode is not yet implemented;
* location has to be allowed manually with chrome pop-up; the pop-ups need to be skipped manually as the TinderBotz handlers are outdated;
* at the moment, the script can only track when swiping using keyboard. This is because Selenium doesn't seem to have capabilities to track DOM events, hence a JS script is injected to recognise user actions.;
* swiping too quickly will result in some profiles not being recorded, or incorrect profiles being recorded against swipe events; this partially follows from the JS script events hack, as there are some sync issues between Selenium and DOM. For best performance allow 5-10 seconds between swipes and swipe only after the script prompts

### Todo:
* save user's session after logging in;
* a better and more reliable way to catch swipes would be to intercept HTTP requests to Tinder API. This would also allow to get unique profile UUIDs;
* save image that was open when the swipe has occured or all of the profile images, to better facilitate learning user's preferences;
* full autonomous swiping mode;