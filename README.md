# Warbler

### A Twitter-like social networking platform that allows users to post, view, like, or unlike messages and view a feed of, follow, or unfollow other users

This project is a part of <a href="https://www.rithmschool.com/">Rithm School's</a> curriculum, and was done in collaboration with my partner <a href="https://github.com/jragni">Jhensen Agni</a> using: 
- Flask
- Python
- PostgreSQL
- SQLAlchemy
- Jinja
- WTForms

## Live Demo
- Here is a live demo of the <a href="https://lillian-warbler.herokuapp.com/">Warbler</a> app.

### Getting started:
1. Clone or fork this repository
2. Setup a virtual environment (inside the repo directory)
* ```python3 -m venv venv```
* ```source venv/bin/activate```
* ```pip3 install -r requirements.txt```
3. Create the database
* ```createdb warbler```
* ```python3 seed.py```
4. Start the Server
* ```flask run```

### Functionality:
- Users can do the following:
  - Login, signup, edit, or delete profile
  - Post, view, like, or unlike messages
  - View a feed of, follow, or unfollow other users
  
## Tests: 
1. Create the test database
* ```createdb warbler-test```
2. Run tests:
* Run all tests: ```python3 -m unittest```
* Run specific file: ```python3 -m unittest test_file_to_run.py```
