"""Enforces the rules proposed in abathur/tdver#1"""
import sys
import os
import re
import argparse
import yaml
import json
import pygit2
from operator import itemgetter


class Repo(pygit2.Repository):
    def git_tags(self):
        return (x[10:] for x in self.references if x.startswith("refs/tags/"))

    def dirty(self):
        return self.describe(dirty_suffix="!!!").endswith("!!!")


class TDVer(
    object
):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    PARTS = ["a", "b", "c", "d"]
    A = 0  # pylint: disable=invalid-name
    B = 1  # pylint: disable=invalid-name
    C = 2  # pylint: disable=invalid-name
    D = 3  # pylint: disable=invalid-name
    POSITIONS = [A, B, C, D]
    INSERTIONS = 0
    DELETIONS = 1
    VERSORT = {"key": itemgetter(0, 1, 2, 3)}

    version_fmt = re.compile(
        r"""
        ([0-9]+)                # match part A
        \.
        ([0-9]+)                # match part B
        \.
        ([0-9]+)                # match part C
        (?:-?                   # looking for either a D part or commits since tag
            (?:
                (?:\d+-\w{8})   # swallow git describe's commits-since-tag fmt. We have to look for this first to lock up its -#commits indicator and avoid accidentally identifying it as our part D
                |
                ([0-9]+)        # match part D
            )
        )*                      # check more than once, since both can be present
    """,
        re.VERBOSE,
    )
    change_fmt = re.compile(
        r"\s*\d+ files? changed, (?:(\d+) insertions?\(\+\),?\s?)?(?:(\d+) deletions?\(\-\),?)?"
    )

    config = {"version": "0.0.0", "tests": "tests/", "bug_tests": "bugs/"}

    def __init__(self, config):
        self.config.update(config)
        path = pygit2.discover_repository(os.getcwd())
        try:
            self.repo = Repo(path)  # present dir
        except pygit2.GitError as e:
            sys.exit("TDVer can only run on a git repository. %r" % e)

        parser = argparse.ArgumentParser(
            description=__doc__,
            prog="tdver",
            conflict_handler="resolve",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        subparsers = parser.add_subparsers(
            description=None, title=None, help=None, metavar="actions:"
        )
        parser.add_argument(
            "--version", action="version", version="%(prog)s " + self.config["version"]
        )

        # TODO: figure out right way to get these
        self.author = pygit2.Signature("TODO", "todo@example.com")
        self.committer = pygit2.Signature("TOODLES", "toodles@example.com")

        # two basic cases: 1.) we are a tdver repo already;
        # 2.) we aren't, and our only viable command is 'start'
        try:
            with open("tdver.json", "r") as conf:
                self.config.update(json.load(conf))
            self.versions = self.find_versions()
            self.last_version = self.find_version()
            self.version = self.last_version.copy()
            self.last_tag = self.version_string()
            self.changes = self.find_changes(self.config.get("tests", "tests/"))
            self.bug_changes = self.find_changes(self.config.get("bug_tests", "bugs/"))

            check_desc = "determine if the repository is in a releasable state"
            check = subparsers.add_parser(
                "check", help=check_desc, description=check_desc
            )
            release_desc = "increment, commit and tag a new release"
            release = subparsers.add_parser(
                "release", help=release_desc, description=release_desc
            )
            support_desc = "create a new version-maintenance branch"
            support = subparsers.add_parser(
                "support", help=support_desc, description=support_desc
            )

            # branch_arg = (("-b", "--branch"), {"help": "not yet implemented"})

            # check.add_argument(*branch_arg[0], **branch_arg[1])
            check.set_defaults(func=self.check)
            # release.add_argument(*branch_arg[0], **branch_arg[1])
            release.set_defaults(func=self.release)
            # support.add_argument(*branch_arg[0], **branch_arg[1])
            support.set_defaults(func=self.support)
        except FileNotFoundError:
            # I kinda doubt this is possible due to meta.py; this probably has to change
            start = subparsers.add_parser(
                "start",
                help="Initialize a new tdver repository and commit the metadata files",
                conflict_handler="resolve",
            )
            start.set_defaults(func=self.start, options=self.config)

        self.parse_command(parser)

    def find_changes(self, target):
        insertions = deletions = 0
        for patch in self.repo.diff(self.last_tag, "HEAD"):
            if patch.delta:
                if patch.delta.old_file.path.startswith(
                    target
                ) or patch.delta.new_file.path.startswith(target):
                    insertions += patch.line_stats[1]
                    deletions += patch.line_stats[2]
        return (insertions, deletions)

    def valid_tags(self):
        """Return a list of tags that appear to be tdver version strings"""
        return [x for x in self.repo.git_tags() if self.valid_tag(x)]

    def valid_tag(self, tag):
        """Return a match object if it looks like a tdver tag, else None"""
        return self.version_fmt.match(tag)

    def parsed_tags(self):
        return [self.parse_tag(x) for x in self.repo.git_tags() if x]

    def parse_tag(self, tag):
        test = self.valid_tag(tag)
        return [int(part) for part in test.groups(0)] if test else None

    def find_version(self):
        # TODO: this presumably raises w/o annotated tags
        return self.parse_tag(self.repo.describe())

    def find_versions(self):
        """Return a list containing our version numbers"""
        return sorted(
            [x for x in self.parsed_tags() if x], reverse=True, **self.VERSORT
        )

    def find_max_version(self):
        return max(self.find_versions(), **self.VERSORT)

    def increment(self, pos, version=None):
        """
        Caution: perhaps it was unwise, but this mutates self.version :O)

        TODO: above is probably a footgun worth fixing?
        """
        if version is None:
            version = self.version
        for part in range(len(version)):
            if part > pos:
                version[part] = 0
            elif part == pos:
                version[part] += 1
        return version

    def incrementable(self, pos, start_version=None):
        """using our current version as the starting point, can a given position increment?
        #we have a current version like 1.2.3.4
            #4 can increment if there is no 1.2.3.5, though it may be ill-advised to let it increment if 1.2.4 exists.
            #3 can increment if there is no 1.2.4.0
            #2 can increment if there is no 1.3.0.0
            #1 can increment if there is no 2.0.0.0
            #
        """
        if start_version is None:
            start_version = self.version
        index = self.versions.index(start_version)

        # top version; the world is our oyster
        if index == 0:
            return True
        else:
            testver = start_version.copy()

            # no sense allowing a "dev" version when a newer bugfix version exists
            # because no more releases are possible anyways
            if pos == self.D:
                pos = self.C

            self.increment(pos, testver)
            if self.versions.index(self.version) > -1:
                return True

        return False

    # can_increment is about whether this position is prevented from incrementing by the state of previously released versions; needs_increment is about whether a position would be required to update based on the repo state.

    def can_increment(self):
        """return a list of incrementable positions"""
        return [self.incrementable(x) for x in self.POSITIONS]

    def a_needs_increment(self):
        # we have changed or removed a test
        if self.changes[self.DELETIONS] > 0:
            return True
        return False

    def b_needs_increment(self):
        # a test has been added
        if self.changes[self.INSERTIONS] > 0:
            return True
        return False

    # save us from increment_b if this is a bug test.
    def c_needs_increment(self):
        # we have insertions in bug_tests:
        if self.bug_changes[self.INSERTIONS] > 0:
            return True
        return False

    def d_needs_increment(self):
        # basically two valid conditions
        # 1 - we have commits since tag
        if self.repo.diff(self.last_tag, "HEAD").stats.files_changed > 0:
            return True
        # 2 - we have uncommitted changes since tag (is this true? should we just ignore uncommitted changes? (this means we basically have to be committed?))
        return self.repo.dirty()

    def needs_increment(self):
        """Returns the index which needs updating, or None."""
        if self.a_needs_increment():
            return self.A
        elif self.b_needs_increment():
            return self.B
        elif self.c_needs_increment():
            return self.C
        elif self.d_needs_increment():
            return self.D
        else:
            return None

    def validate_version(self):
        """Fail a CI check if the build hasn't been incremented following our rules."""
        needs_increment = self.needs_increment()
        if needs_increment is not None:
            new_version = self.version.copy()
            self.increment(needs_increment, new_version)
            if self.incrementable(
                needs_increment
            ):  # these messages can be vastly better
                out = []
                out += [" Current version: %s" % self.version_string()]
                out += ["Required version: %s" % self.version_string(new_version)]
                out += [
                    "Version part %s must increment for this changeset per TDVer rules."
                    % self.PARTS[needs_increment].title()
                ]
            else:
                # these changes require an increment to part X, but part X may not increment because the next version already exists.
                out = [
                    "This changeset requires an increment to the %s version part per TDVer rules, but the specified version (%s) already exists."
                    % (self.PARTS[needs_increment], self.version_string(new_version))
                ]
            sys.exit("\n".join(out))

        # Print verstring to stdout for piping; effectively:
        # By our rules this version is valid, but you can pipe to another cli/validator
        # which may object for other reasons; i.e.:
        #   because not all verstring locations match
        #   version-sensitive tests didn't pass
        print(self.version_string())
        sys.exit(0)  # current version valid

    def update_version(self):
        """
        Increment the authoritative version number if necessary.
        """
        if self.increment_version():
            self.write_version()
            return True
        return False

    def increment_version(self):
        """Increment the tdver-internal version number."""
        part = self.needs_increment()
        if part is not None:
            return self.increment(part)
        return None

    def version_string(self, version=None):
        if version is None:
            version = self.version
        if version[self.D] > 0:
            return "%d.%d.%d-%d" % tuple(version)
        return "%d.%d.%d" % tuple(version[self.A : self.D])

    def write_version(self):
        """Write the tdver-internal version to file, making it authoritative."""

        with open("tdver.json", "w") as conf:
            self.config["version"] = self.version_string()
            json.dump(self.config, conf, sort_keys=True, indent=4)

    def tag_version(self):
        """Creates a tag with the current version."""
        verstring = self.version_string()
        self.repo.create_tag(
            verstring,
            self.repo.head.peel().oid,
            pygit2.GIT_OBJ_COMMIT,
            self.author,
            "Version %s released via TDVer" % verstring,
        )

    @staticmethod
    def format_tip(tip):
        return "%s.x" % ".".join(tip)

    def get_tip(self, version=None):
        if version is None:
            version = self.version
        # this is the most recent of all releases; it is already "supported" by the edge development branch/master
        if version == max(self.versions):
            return None

        # fetch all of our current major revision's releases
        relevant_versions = filter(
            lambda x: x[self.A] == version[self.A], self.versions
        )

        # can we support the major version?
        if version[self.B] == max(map(lambda x: x[self.B], relevant_versions)):
            # most recent minor release under this major; valid for supporting the major.
            return version[self.A : self.B]

        relevant_versions = filter(
            lambda x: x[self.B] == version[self.B], relevant_versions
        )

        # can we support the minor version?
        if version[self.C] == max(map(lambda x: x[self.C], relevant_versions)):
            return version[self.A : self.C]

        # it makes no sense to provide long-term support for a bug or dev release, so we're done.
        return None

    # tdver start [at version <version>] | create the yml for enforcing tdver in current branch, possibly with a starting version
    # open question: should I be raising errors or notifying the user if this already appears to be a tdv repo (it doesn't seem to matter; this isn't a destructive process and w/o a release does nothing--but if I make a decorator for this purpose I might as well)
    # open question: need we do anything with the version at this point?
    def start(self, options):  # pylint: disable=unused-argument
        validate_cmd = "tdver check"
        # print(options)
        try:
            self.version = options.version
        except AttributeError:
            # you literally can't release this version. even a dev release would be t0.0.0-1
            # probably need to be really sure we won't ever accidentally get here, yeah?
            # may be possible to create an "unreleasable" t0.0.0-0 tag?
            self.version = [0, 0, 0, 0]

        else:
            raise NotImplementedError(
                "No support yet for specifying a start version; making sure TDver actually works for new projects before letting you risk transitioning an existing project (unless you're persistent/convinced enough to implement this yourself. :)"
            )

        # TODO: the CI scaffolding is a good idea, but make it smrt or safe
        with open(".travis.yml", "a+") as yml:
            # load existing conf
            yml.seek(0, 0)
            conf = yaml.safe_load(yml.read())
            # make our changes
            if conf:
                if "script" in conf:
                    # script could be a str or list; are we already in either?
                    existing = conf["script"]
                    if validate_cmd not in existing:
                        if isinstance(existing, str):
                            conf["script"] = [validate_cmd, conf["script"]]
                        elif isinstance(existing, list):
                            conf["script"] = [validate_cmd] + conf["script"]
            else:
                # sensible defaults?
                conf = {"script": validate_cmd}

            # save them
            yml.seek(0, 0)
            yml.truncate()
            yml.write(yaml.dump(conf, default_flow_style=False))

        self.write_version()
        self.repo.index.read()
        for filename in (".travis.yml", "tdver.json"):
            self.repo.index.add(filename)
        self.repo.index.write()

        new = self.version_string()

        tree = self.repo.index.write_tree()
        self.repo.create_commit(
            "refs/heads/main",  # TODO: dynamically use our branch
            self.author,
            self.committer,
            f"tdver: init at {new}\n\ndetailed commit message",
            tree,  # binary string representing the tree object ID
            [],  # list of binary strings representing parents of the new commit
        )

        self.tag_version()

        print("TDVer repository initialized.")

        return sys.exit(0)

    def check(self, options):  # pylint: disable=unused-argument
        return self.validate_version()

    # create the YML file in branch, set it at version
    # tdver release [branch] | create a release tag, probably push it
    # advanced: push/don't, remote target, etc.
    def release(self, options):  # pylint: disable=unused-argument
        previous = self.version_string()
        if self.update_version():
            new = self.version_string()

            self.repo.index.read()
            for filename in (".travis.yml", "tdver.json"):
                self.repo.index.add(filename)
            self.repo.index.write()

            print("Updated version.")
            print("old: %s" % previous)
            print("new: %s" % new)
            # tree = r.TreeBuilder(self.repo.head.tree.oid)
            self.repo.create_commit(
                "refs/heads/main",  # TODO: dynamically use our branch
                self.author,
                self.committer,
                f"tdver: {previous} -> {new}\n\ndetailed commit message",
                self.repo.head.peel().tree.oid,  # binary string representing the tree object ID
                [
                    self.repo.head.target
                ],  # list of binary strings representing parents of the new commit
            )
            self.tag_version()
            # push to origin? seems like this should be an option, even if it's default
            # push could mean both tags and changes
            return sys.exit(0)
        else:
            # this is a really poor message. In some cases we get here because we've already released the most-current possible version
            # but in others we get here because we can't increment
            return sys.exit("A release doesn't seem to be possible.")

    # tdver support [version] | create a branch and yml for a supported sub-release behind the primary release branch
    def support(self, options):  # pylint: disable=unused-argument
        tip = self.get_tip()
        if tip:
            tipstring = self.format_tip(tip)

            self.repo.branches.local.create(tipstring)
            # might not need a special YML; it seems like we can just infer this from the repo
            print("Maintenance branch %s created." % tipstring)
            return sys.exit(0)

        return sys.exit(
            "This version can't be maintained; either it is the edge version or the minor and patch positions may not increment."
        )

    @staticmethod
    def parse_command(parser):
        args = parser.parse_args()
        if "func" in args:
            args.func(args)


def main():
    from .meta import config

    TDVer(config)
