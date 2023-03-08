# Instal Python environment and packages on a server without internet connection

0. Create mirror folder and ansible distro foder on `server_no_net`

    ```bash
    MIRROR="${HOME}/python-mirror"
    [[ ! -d ${MIRROR}/src/packages ]] && mkdir -p ${MIRROR}/src/packages

    DISTRO="/opt/ansible"
    [[ ! -d ${DISTRO} ]] && sudo mkdir -p ${DISTRO};  sudo chown asaramet:rz ${DISTRO}
    ```

1. Create a virtual env on local pc, create a local mirror with ansible and dependencies

    ```bash
    virtualenv -p python3 ansible-mirror
    cd ansible-mirror
    . bin/activate
    pip install python-pypi-mirror
    pypi-mirror download -d src/packages pip setuptools wheel Cython setuptools-rust cryptography==3.4 ansible

    rsync -uav src/packages/* server_no_net:WORK/src/packages
    ```

2. Download the source code on local machine and copy it to `server_no_net`

    ```bash
    mkdir -p ${HOME}/ansible-mirror/src && cd src
    VERSION="3.9.15"
    wget https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz
    wget https://files.pythonhosted.org/packages/01/a1/dee41b7a79b53477dfdb1257f805c99d7d27e0a2eb41104e7d3cb6b2b778/python-pypi-mirror-5.0.1.tar.gz

    cd ..
    rsync -uavr src/* server_no_net:python-mirror/src
    ```

3. Build the distro in user specific folder on `server_no_net`. For example ${HOME}/python-mirror

    ```bash
    sudo apt install libffi-dev libssl-dev zlib1g-dev

    VERSION="3.9.15"

    [[ ! -d ${MIRROR}/build ]] && mkdir -p ${MIRROR}/build
    cd ${MIRROR}/build

    tar zxvf ${MIRROR}/src/Python-${VERSION}.tgz
    cd Python-${VERSION}
    ./configure --prefix=${DISTRO} --enable-optimizations
    make
    make install

    cd ${MIRROR} && rm build -rfv
    ```

4. The 'envs' script in /opt/ansible that has to be sourced to set local python variables:

    ```bash
    #!/usr/bin/env bash

    # User defined environments, bins and libs

    variables() {
    local base_dir='/opt/ansible'
    PATH="${base_dir}/bin:${PATH}"
    if [[ -z ${LD_LIBRARY_PATH} ]]; then
      LD_LIBRARY_PATH="${base_dir}/lib"
    else
      LD_LIBRARY_PATH="${base_dir}/lib:${LD_LIBRARY_PATH}"
    fi

    if [[ -z ${INCLUDE} ]]; then
      INCLUDE="${base_dir}/include"
    else
      INCLUDE="${base_dir}/include:${INCLUDE}"
    fi

    if [[ -z ${MANPATH} ]]; then
      MANPATH="${base_dir}/share/man"
    else
      MANPATH="${base_dir}/share/man:${MANPATH}"
    fi

    # PYTHON
    p_version='3.9'
    if [[ -z ${PYTHONPATH} ]]; then
      PYTHONPATH="${base_dir}/lib/python${p_version}/site-packages"
    else
      PYTHONPATH="${base_dir}/lib/python${p_version}/site-packages:${PYTHONPATH}"
    fi

    INCLUDE="${base_dir}/include/python${p_version}:${INCLUDE}"

    # Include the ansible.cfg file as env variable making it the top level choise
    export ANSIBLE_CONFIG=${base_dir}/inventory/ansible.cfg
    }

    variables
    ```

## Installing Ansible

1. Source the local python environment

    ```bash
    . /opt/ansible/envs
    ```

2. Verify if pip is available and using local build

    ```bash
    python3 -m pip -V
    which pip3
    ```

    If pip module is no available install it:

    ```bash
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py --user
    ````

3. Link pip

    ```bash
    cd ${DISTRO}/bin
    ln -s pip3 pip
    ```

4. Create localhost pip mirror on `server_no_net`

    ```bash
    cd $MIRROR/src

    pip3 install python-pypi-mirror-5.0.1.tar.gz --no-index

    cd $MIRROR
    pypi-mirror create -d ${MIRROR}/src/packages -m ${MIRROR}/mirror
    ```

5. Start repository server on `server_no_net`

    ```bash
    cd $MIRROR
    python3 -m http.server
    ```

6. Install ansible on `server_no_net`
On `server_no_net` there is a link to pip repos, so ansible can be installed without mirror

    ```bash
    pip install ansible
    ```

    With mirror:

    ```bash
    . /opt/ansible/envs

    LANG="en_US.utf8"
    export CRYPTOGRAPHY_DONT_BUILD_RUST=1
    pip install -i http://127.0.0.1:8000/mirror cryptography==3.4
    pip install -i http://127.0.0.1:8000/mirror ansible
    ```

7. Install AOSCX Ansible Collection
    Official Webpage: <https://developer.arubanetworks.com/aruba-aoscx/docs/getting-started-with-ansible-and-aos-cx>
    GitHub repository: <https://github.com/aruba/aoscx-ansible-collection>

    Check the right path to `collections` folder

    ```bash
    ansible-galaxy collection list

    # /opt/ansible/lib/python3.9/site-packages/ansible_collections
    Collection                    Version
    ----------------------------- -------
    ....
    ```

    Install the collection

    ```bash
    ansible-galaxy collection install arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

8. Update packages with pip
  
    ```bash
    pip install --upgrade pip
    pip list --outdated # to view the outdated packages
    pip install -U `pip list --outdated | awk 'NR>2 {print $1}'` # starting with the second line add first column (package name)
    ansible-galaxy collection install -U arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

9. Install AOSCX Ansible Role

    ```bash
    ansible-galaxy install arubanetworks.aoscx_role # -p /opt/ansible/lib/python3.9/site-packages/ansible_roles
    cd $HOME/.ansible/roles/arubanetworks.aoscx_role
    ansible-galaxy install -r requirements.yml
    pip install requests pyaoscx
    ```
  