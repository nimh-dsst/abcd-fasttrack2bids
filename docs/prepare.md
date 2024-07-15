# NDA Data Preparation

## 1. Preparing abcd_fastqc01.txt

1. Go to https://nda.nih.gov and login to your account (click `LOGIN` on the top right)
1. Click on the `Get Data` > `Get Data` tab in the menu up top
1. Go to `Data Dictionary` > `Data Structures` on the left
1. Search for `abcd_fastqc01`
1. Click the checkbox to the left of `ABCD Fasttrack QC Instrument`
1. Click `ADD TO WORKSPACE` in the bottom right
1. Click on the little filter icon with the number 1 on it in the top right
1. Click `SUBMIT TO FILTER CART` in the bottom right of this new pane
1. Wait for the `Filter Cart (0)` in the top right to change to `Filter Cart (1)`, then click on it
1. Click on the `Filter Cart (1)` icon in the top right
1. Click on `Create Data Package/Add Data to Study`
1. Click `Create Data Package`
    - Name the package something informative like `abcdqcYYYYMMDD` (note: special characters are not allowed)
    - Select Only `Include documentation`
    - Click `Create Data Package`
1. Click on `My Account` > `Data Packages` on the top right to find your new package. You should see the data package with a status of `Creating Package`. It takes roughly 10 minutes for the NDA to create this package. When it is ready to download the status will change to `Ready to Download`.

## 2. Preparing collection 2573 imaging data

The instructions for this package are similar to those for the `abcd_fastqc01.txt` package.

1. Follow steps 1 and 2 from above
1. Click on `Data from Labs` on the left
1. Search for `abcd study`
1. Click on the checkbox to the left of `ABCD Study`, making sure that the `COLLECTION ID` is `2573`
1. Follow steps 6-11 from above. Step 9 may take a couple of hours for the `Filter Cart` to update.
1. When you follow step 12 from above, make sure to also click the box that says `Include Associated Data Files` before clicking `Create Data Package`

You can check the status of this package by navigating back to the `Data Packages` tab within your profile. You should see your newly created package at the top of the table with a status of `Creating Package`. This data package is 300+TB in size and may take up to a day to be created. Wait until the status changes to `Ready to Download` before proceeding. Make note of this Package ID as it will be needed to convert.

## 3. `downloadcmd` preparation

To use 'downloadcmd' it is necessary to set up a keyring. See the `Updating Stored Passwords with keyring` step on the [nda-tools repository](https://github.com/NDAR/nda-tools) README.md for more information.

The contents of `~/.config/python_keyring/keyringrc.cfg` should be:

```shell
[backend]
 default-keyring=keyrings.alt.file.PlaintextKeyring
 keyring-path=/tmp/work
```

After the contents of `keyringrc.cfg` have been properly edited, run these commands (replacing `<username>` with your actual NDA username) to see if your password for nda-tools is up to date. Be aware that this will display your password in the terminal:

```shell
cd
git clone https://github.com/nimh-dsst/abcd-fasttrack2bids.git
cd ~/abcd-fasttrack2bids
poetry install
poetry run python -c 'import keyring ; print(keyring.get_password("nda-tools", "<username>"))'
```

If the correct password is not returned, then run the following to fix the NDA credentials issue (replacing `<username>` with your actual NDA username and `<password>` with your actual NDA password):

```shell
cd ~/abcd-fasttrack2bids
poetry run python -c 'keyring.set_password("nda-tools", "<username>", "<password>")'
```

If you are encountering the following error upon running this command, then it is likely that your versions of `keyring` and `keyring.alt` are out of date. Make sure you have installed python poetry from the README.md installation instructions and that the `keyring` and `keyrings.alt` versions respectively are `23.13.1` and `3.1` or greater.

`ModuleNotFoundError: No module named 'keyrings'`

**Important Note**: your NDA password and keyring password cannot differ. It's also important to be careful if you use exclamation marks or other special characters in the password that can trigger keyring issues/errors.
