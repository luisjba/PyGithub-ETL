#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitDump class definition 
@datecreated: 2021-09-16
@lastupdated: 2021-09-17
@author: Jose Luis Bracamonte Amavizca
"""
# Meta informations.
__author__ = 'Jose Luis Bracamonte Amavizca'
__version__ = '0.0.1'
__maintainer__ = 'Jose Luis Bracamonte Amavizca'
__email__ = 'me@luisjba.com'
__status__ = 'Development'

import os, sys
from datetime import datetime
from posixpath import join
from github import Github, GithubException
from github.Repository import Repository
from .db import Connection
from .utils import print_fail, print_okgreen, print_okblue

class GitDump():
    def __init__(self, token: str, repo_fullname: str, db_file: str = "data/data.db", base_path: str = "", schemas_dir="schemas") -> None:
        self._date_format:str = "%Y/%m/%d %H:%M:%S"
        self.g: Github = Github(token)
        try:
            self.repo:Repository = self.g.get_repo(repo_fullname)
        except GithubException as e:
            if e.status == 401:
                print_fail("The token is invalid, please privide a new valid token")
            elif e.status == 404:
                print_fail("The repository '{}' was not found, try with with a diferent repository name.".format(repo_fullname))
            else:
                print_fail("GitHub error: {}".format(e))
            sys.exit(1)
        self.db_file:str = db_file
        self.base_path:str = base_path
        self.db_conn:Connection = Connection(self.base_path, db_file)
        print_okgreen("SQLite connected to:{}".format(self.db_conn.db_file))
        self._init_db(schemas_dir)

    def _init_db(self, schemas_dir="schemas"):
        """Checks the db connection and initialize the database"""
        schemas_dir = os.path.join(self.base_path, schemas_dir) if not schemas_dir[0] == "/" else schemas_dir
        if not os.path.isdir(schemas_dir):
            print_fail("'{}' is an invalid directory. Provide a valid directory to find the schemas for SQLite tables".format(schemas_dir))
            sys.exit(1)
        schemas:list = ['repo', 'branch']
        schame_dict = {schema:"{}/{}.sql".format(schemas_dir, schema) for schema in schemas}
        if self.db_conn is not None and len(schame_dict) > 0:
            for t,t_file  in schame_dict.items():
                if not os.path.isfile(t_file):
                    print_fail("Schema file '{}' does not exists".format(t_file))
                    continue
                result = self.db_conn.execute_query_fetch('sqlite_master',['name'],{'type':'table', 'name':t})
                if len(result) > 0 : # The table already axists in the database
                    continue 
                with open(t_file, 'r') as file:
                    if self.db_conn.create_table(file.read()):
                        print_okgreen("Created the table {} into SQLite db: '{}'".format(t, self.db_conn.db_file))

    def sync_repo(self):
        """This function perform the repo syncronization into the SQLite db"""
        repo_data = {
            "name": self.repo.name,
            "owner": self.repo.owner.login,
            "fullname": self.repo.full_name,
            "description": self.repo.description,
            "url": self.repo.url,
            "pushed_date": int(self.repo.pushed_at.timestamp()),
            "created_date": int(self.repo.created_at.timestamp()),
            "size": self.repo.size,
            "stars": self.repo.stargazers_count,
            "forks": self.repo.forks_count,
            "watchers": self.repo.watchers_count,
            "language": self.repo.language,
            "topics": ",".join(self.repo.get_topics()),
        }
        db_repo = self.db_conn.get_repo(self.repo.full_name)
        if db_repo is None:
            db_repo = self.db_conn.add_repo(repo_data)
            if db_repo is None:
                print_fail("Failed insert the new repository '{}' into SQLite db".format(self.repo.full_name))
                sys.exit(1)
            else:
                print_okgreen("Respository '{}'  succesfully inserted into SQLite db".format(self.repo.full_name))
        else:
            if db_repo["pushed_date"] < repo_data["pushed_date"]:
                print_okblue("Trying to update repo '{}' from {} to {} ".format(
                    self.repo.full_name,
                    datetime.fromtimestamp(db_repo["pushed_date"]).strftime(self._date_format),
                    datetime.fromtimestamp(repo_data["pushed_date"]).strftime(self._date_format)
                ))
                db_repo = self.db_conn.update_repo(repo_data)
                print_okgreen("Respository '{}' succesfully sincronized into SQLite db.".format(self.repo.full_name))
            else:
                print_okblue("Respository '{}' is up to date.".format(self.repo.full_name))

    def sync_branches(self):
        """Syncornize the Branches of the repository"""
        db_repo = self.db_conn.get_repo(self.repo.full_name)
        if db_repo is None:
            print_fail("The repository '{}' dos not exists in the SQLite db. Try first 'sync_repo' function".format(self.repo.full_name))
            sys.exit(1)
        for branch in self.repo.get_branches():
            branch_data = {
                "repo_id": db_repo["id"],
                "name": branch.name,
                "commit_sha": branch.commit.sha,
                "protected": 1 if branch.protected else 0,
            }
            db_branch = self.db_conn.get_branch(db_repo["id"], branch.name)
            if db_branch is None:
                db_branch = self.db_conn.add_branch(db_repo["id"], branch_data)
                if db_branch is None:
                    print_fail("Failed insert the branch '{}:{}' into SQLite db".format(self.repo.full_name, branch.name))
                else:
                    print_okgreen("Branch '{}:{}' succesfully inserted into SQLite db".format(self.repo.full_name, branch.name))
            else:
                if not (db_branch["commit_sha"] == branch_data["commit_sha"] ) :
                    print_okblue("Trying to update branch '{}:{}' from commit  {} to {} ".format(
                            self.repo.full_name, branch.name, db_branch["commit_sha"], branch_data["commit_sha"]
                        ))
                    db_branch = self.db_conn.update_branch(branch_data)
                    print_okgreen("Branch '{}:{}' succesfully sincronized into SQLite db.".format(self.repo.full_name, branch.name))
                else:
                    print_okblue("Branch '{}:{}' is up to date.".format(self.repo.full_name, branch.name))


    

