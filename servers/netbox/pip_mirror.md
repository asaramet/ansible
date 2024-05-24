# Download pip packages

As the server may not have an internet connection to download the required pip packages, it is possible to:

- download the required pip packages locally,
- archive and send them to the server,
- install the packages from the local folder on the server.

## Install pyenv for using multiple Python versions on Arch Linux localhost

For the current requirements Python3.11 is recommended, so install an extra python version, to create a venv with it.

[pyenv documentation](https://man.archlinux.org/man/pyenv.1.en)

```bash
sudo pacman -Syu pyenv
```

Append the following to `$HOME/.bashrc`

```bash
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)" 
fi
```

Restart the shell to use `pyenv` command properly.

Install and download required python version, here for example, 3.11.2

```bash
pyenv install 3.11.2
```

After you installed the version it can be used as a system command with Python version number, i.e:

```bash
python3.11 script.py
```

```bash
# pyenv commands
pyenv install <version>
pyenv uninstall <version>
pyenv versions # list python versions available
pyenv shell <version> # allows to use the python version in this shell
```

## Download packages in a virtual environment with pip

```bash
pyenv shell 3.11.2
python3.11 -m venv pip-packages
cd pip-packages
ln -s ../requirements.txt
. bin/activate

mkdir packages
cd packages
pip download -r ../requirements.txt
```
