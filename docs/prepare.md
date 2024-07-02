# NDA Data Preparation

## 1. Preparing abcd_fastqc01.txt

1. Go to https://nda.nih.gov and click `LOGIN` on the top right
1. Click on the `Get Data` > `Get Data` tab up top
1. Go to `Data Dictionary` > `Data Structures` on the left
1. Search for `abcd_fastqc01`
1. Click the checkbox to the left of `ABCD Fasttrack QC Instrument`
1. Click `ADD TO WORKSPACE` in the bottom right
1. Click on the top right on the little filter icon with the number 1 on it
1. Click `SUBMIT TO FILTER CART` in the bottom right of this new pane
1. Wait for the `Filter Cart (0)` to change to `Filter Cart (1)`
1. Click on the `Filter Cart (1)` icon in the top right
1. Click on `Create Data Package/Add Data to Study`
1. Click `Create Data Package`
    - Name the package something informative like `abcdqcYYYYMMDD` (note: special characters are not allowed)
    - Select Only `Include documentation`
    - Click `Create Data Package`
1. Navigate to your NDA dashboard and from your NDA dashboard, click `Data Packages`. You should see the data package that you just created with a status of `Creating Package`. It takes roughly 10 minutes for the NDA to create this package.
1. When the Data Package is ready to download the status will change to `Ready to Download`

## 2. Preparing collection 2573 imaging data

1. Go to https://nda.nih.gov and click `LOGIN` on the top right
1. Click on the `Get Data` > `Get Data` tab up top
1. Click on `Data from Labs` on the left
1. Search for `abcd study`
1. Click on the checkbox to the left of `ABCD Study` which you'll see on the right is collection `2573`
1. Click `ADD TO WORKSPACE` in the bottom right
1. Click on the top right on the little filter icon with the number 1 on it
1. Click `SUBMIT TO FILTER CART` in the bottom right of this new pane
1. Wait for the `Filter Cart (0)` to change to `Filter Cart (1)`, this may take a couple hours...
1. Click on the `Filter Cart (1)` icon in the top right
1. Click on `Create Data Package/Add Data to Study`
1. Click `Create Data Package`
    - Name the package something informative like `abcdYYYYMMDD` (note: special characters are not allowed)
    - Check the box that says `Include Associated Data Files`
    - Click `Create Data Package`

This data package is 300+TB in size and may take up to a day to be created. You can check the status of this package by navigating back to the `Data Packages` tab within your profile. You should see your newly created package at the top of the table with a status of `Creating Package`. Wait until the status changes to `Ready to Download` before proceeding. Make note of this Package ID as it will be needed to convert.

## 3. `downloadcmd` preparation

The `Updating Stored Passwords with keyring` step on the [nda-tools repository](https://github.com/NDAR/nda-tools) README.md is still necessary.

The contents of `~/.config/python_keyring/keyringrc.cfg` should be:

```
[backend]
 default-keyring=keyrings.alt.file.PlaintextKeyring
 keyring-path=/tmp/work
```

After the contents of `keyringrc.cfg` have been properly edited, run these commands to see if your password for nda-tools is up to date. Be aware that this will display your password in the terminal:

```
python3
import keyring
keyring.get_password("nda-tools", "<username>")
```

If the correct password is not returned, then running `keyring.set_password("nda-tools", "<username>", "<password>")` should fix the issue.

**Important Note**: your NDA password and keyring password cannot differ. It's also important to be careful if you use exclamation marks or other special characters in the password that can trigger keyring issues/errors.
