# ApacheMiner
COMP0104: Software Development Practice Coursework 2, which investigates the evidence that projects are adopting Test-First or Test-Driven Approach and how strictly they follow the practice.


## :rocket: Running the project 

this project uses poetry to manage dependencies, and the virtual environment. This project is using python3.12, so make sure you are using it 

```bash
python3.12 -m pip install poetry 
```


### :inbox_tray: Installing dependencies 

To install the dependencies, run the following commands in the root directory of the project


```bash
poetry install 
```

### :gear: running commands

to run the set commands in the project, you can use the following command 


```bash 
poetry run <command>

```

or you can run the cli using 
```bash 
poetry run cli
```

you can alternatively run the shell and directly run the cli 

```bash
poetry shell
python3 src
```

## :shield: Running Test 

before pushing, make sure you run the noxfile to ensure that everything is working fine
```bash 
poetry run nox 
```

this will run the entire test suite, and ensure that linting, formatting, type hinting is correct.


## :whale: Using docker 

You can also use docker to run the project, to build the docker image, you can use the following command 

```bash
docker build -t apache-miner .
```

to run the docker image, you can use the following command 

```bash
docker run -it apache-miner <command>
```
