import configparser
import os
import os.path as osp
import tarfile

import requests
import yaml


class PKGBUILDGenerator(object):
    def __init__(
        self,
        cran_mirror="https://cran.r-project.org",
        bioconductor_mirror="https://bioconductor.org",
        cran_packages_file=None,
        bioconductor_packages_file1=None,
        bioconductor_packages_file2=None
    ):
        """PKGBUILDGenerator class
        param: cran_mirror, CRAN mirror
        param: bioconductor_mirror, Bioconductor mirror
        param: cran_packages_file, pre-downloaded PACKAGES file from https://cran.r-project.org/src/contrib/PACKAGES
        param: bioconductor_packages_file1, pre-downloaded PACKAGES file from https://bioconductor.org/packages/release/bioc/src/contrib/PACKAGES
        param: bioconductor_packages_file1, pre-downloaded PACKAGES file from https://bioconductor.org/packages/release/data/annotation/src/contrib/PACKAGES
        """
        self.cran_mirror = cran_mirror
        self.bioconductor_mirror = bioconductor_mirror
        self.repos = ["cran", "bioconductor", "github"]
        # cache all pkg metadata in CRAN
        if cran_packages_file:
            with open(cran_packages_file, 'r') as f:
                self.cran_descs = f.read().split('\n\n')
        else:
            r_cran = requests.get(
                f"{cran_mirror}/src/contrib/PACKAGES")
            if r_cran.status_code == requests.codes.ok:
                self.cran_descs = r_cran.text.split('\n\n')
            else:
                raise RuntimeError(
                    f"Failed to get CRAN descriptions due to: {r_cran.status_code}: {r_cran.reason}")
        # cache all pkg metadata in Bioconductor
        if bioconductor_packages_file1 and bioconductor_packages_file2:
            with open(bioconductor_packages_file1, 'r') as f1, open(bioconductor_packages_file2, 'r') as f2:
                self.bioconductor_descs = [
                    f1.read().split('\n\n'),
                    f2.read().split('\n\n')
                ]
        else:
            bioconductor_descs = []
            for url in [f"{self.bioconductor_mirror}/packages/release/bioc/src/contrib/PACKAGES",
                        f"{self.bioconductor_mirror}/packages/release/data/annotation/src/contrib/PACKAGES",
                        f"{self.bioconductor_mirror}/packages/release/data/experiment/src/contrib/PACKAGES"
                        ]:
                r = requests.get(url)
                if r.status_code == requests.codes.ok:
                    bioconductor_descs.append(r.text.split('\n\n'))
                else:
                    bioconductor_descs.append([])
            x = set([len(_) for _ in bioconductor_descs])
            if len(x) == 1 and list(x)[0] == 0:
                raise RuntimeError(
                    f"Failed to get Bioconductor descriptions ")
            self.bioconductor_descs = bioconductor_descs
        self.exclude_pkgs = {
            "base",
            "boot",
            "class",
            "cluster",
            "codetools",
            "compiler",
            "datasets",
            "foreign",
            "graphics",
            "grDevices",
            "grid",
            "KernSmooth",
            "lattice",
            "MASS",
            "Matrix",
            "methods",
            "mgcv",
            "nlme",
            "nnet",
            "parallel",
            "rpart",
            "spatial",
            "splines",
            "stats",
            "stats4",
            "survival",
            "tcltk",
            "tools",
            "utils",
            "R"
        }
        self.arch_licenses = [
            "AGPL",
            "AGPL3",
            "APACHE",
            "Apache",
            "Artistic2.0",
            "Boost",
            "CCPL",
            "CDDL",
            "CPL",
            "EPL",
            "FDL",
            "FDL1.2",
            "FDL1.3",
            "GPL",
            "GPL2",
            "GPL3",
            "LGPL",
            "LGPL2.1",
            "LGPL3",
            "LPPL",
            "MPL",
            "MPL2",
            "PHP",
            "PSF",
            "PerlArtistic",
            "RUBY",
            "Unlicense",
            "W3C",
            "ZPL"
        ]

    def has_fortran_src(self, tarfile_object):
        """
        return True if Fortran src file is found in the source tarball
        """
        for name in tarfile_object.getnames():
            if name.endswith(".f") or name.endswith(".f90") or name.endswith(".for"):
                return True
        return False

    def get_bioconductor_ver(self, bio_name, return_idx=False):
        """ get pkg version from Bioconductor
        args:
            bio_name: pkg name in Bioconductor, case sensitive
            return_idx: return idx of self.bio_descs
        return: pkg version in Bioconductor
        raise: RuntimeError if not found
        """
        config = configparser.ConfigParser()
        for idx, descs in enumerate(self.bioconductor_descs):
            for _ in descs:
                if _.startswith(f"Package: {bio_name}\n"):
                    config.read_string(f"[{bio_name}]\n" + _)
                    if return_idx:
                        return config[bio_name]["version"], idx
                    else:
                        return config[bio_name]["version"]

        raise RuntimeError(f"{bio_name} not found in Bioconductor")

    def get_cran_ver(self, cran_name):
        """ get pkg version from CRAN
        param: cran_name: pkg name in CRAN, case sensitive
        return: pkg version in CRAN
        raise: RuntimeError if not found
        """
        config = configparser.ConfigParser()
        for _ in self.cran_descs:
            if _.startswith(f"Package: {cran_name}\n"):
                config.read_string(f"[{cran_name}]\n" + _)
                break
        if cran_name not in config:
            raise RuntimeError(f"{cran_name} not found in CRAN")

        return config[cran_name]["version"]

    def get_github_ver(self, github_owner, github_repo):
        """get rpkgname version from github
        param: github_owner: github repo owner
        param: github_repo: github repo name, this is also the rpkgname
        return: version
        raise: RuntimeError if not found
        for example, https://github.com/ManuelHentschel/vscDebugger
        github_owner=ManuelHentschel
        github_repo=vscDebugger
        """
        # currently, we only check for release, not git tags
        release_url = f"https://api.github.com/repos/{github_owner}/{github_repo}/releases"
        r = requests.get(release_url)
        if r.status_code == requests.codes.ok:
            if r.json():
                return r.json()[0]["name"]
        else:
            raise RuntimeError(
                f"could not find version in https://github.com/{github_owner}/{github_repo} due to {r.status_code}: {r.reason}")

    def isInCran(self, cran_name):
        """
        return True if `cran_name` is found in CRAN
        """
        for _ in self.cran_descs:
            if _.startswith(f"Package: {cran_name}\n"):
                return True

        return False

    def parse_description(self, rpkgname, repo="cran", clean=True):
        """
        parse DESCRIPTION file of `rpkgname`
        args:
            rpkgname: pkgname in R (CRAN, Bioconductor, Github), for github, rpkgname should be github_owner/github_repo
            repo: repo that pkgname is in, CRAN, Bioconductor, github
            clean: delete files if True
        """
        if repo not in self.repos:
            raise RuntimeError(f"Only these repos is supported: {self.repos}")
        result = {
            "repo": repo,
            "rpkgname": rpkgname,
            "rpkgver": None,
            "title": None,
            "arch": "any",
            "r_depends": [],
            "depends": ["r"],
            "r_optdepends": [],
            "optdepends": [],
            "makedepends": [],
            "systemrequirements": None,
            "license": None,
            "license_filename": None,
            "source": None,
            "project_url": None
        }
        if repo == "bioconductor":
            rpkgver, idx = self.get_bioconductor_ver(rpkgname, return_idx=True)
            if idx == 0:
                url = f"{self.bioconductor_mirror}/packages/release/bioc/src/contrib/{rpkgname}_{rpkgver}.tar.gz"
                source = "https://bioconductor.org/packages/release/bioc/src/contrib/${_pkgname}_${_pkgver}.tar.gz"
            elif idx == 1:
                url = f"{self.bioconductor_mirror}/packages/release/data/annotation/src/contrib/{rpkgname}_{rpkgver}.tar.gz"
                source = "https://bioconductor.org/packages/release/data/annotation/src/contrib/${_pkgname}_${_pkgver}.tar.gz"
            elif idx == 2:
                url = f"{self.bioconductor_mirror}/packages/release/data/experiment/src/contrib/{rpkgname}_{rpkgver}.tar.gz"
                source = "https://bioconductor.org/packages/release/data/experiment/src/contrib/${_pkgname}_${_pkgver}.tar.gz"
            result["project_url"] = 'https://bioconductor.org/packages/${_pkgname}'
        elif repo == "cran":
            rpkgver = self.get_cran_ver(rpkgname)
            url = f"{self.cran_mirror}/src/contrib/{rpkgname}_{rpkgver}.tar.gz"
            source = "https://cran.r-project.org/src/contrib/${_pkgname}_${_pkgver}.tar.gz"
            result["project_url"] = 'https://cran.r-project.org/package=${_pkgname}'
        elif repo == "github":
            github_owner, github_repo = rpkgname.strip('/').split('/')
            result["rpkgname"] = github_repo
            result["github_owner"] = github_owner
            result["github_repo"] = github_repo
            result["project_url"] = f"https://github.com/{github_owner}/{github_repo}"
            github_rpkgver = self.get_github_ver(github_owner, github_repo)
            rpkgver = github_rpkgver.lstrip('v')
            url = f"https://github.com/{github_owner}/{github_repo}/releases/download/{github_rpkgver}/{github_repo}_{rpkgver}.tar.gz"
            if github_rpkgver.startswith('v'):
                source = f"https://github.com/{github_owner}/{github_repo}/releases/download/v${{pkgver}}/${{_pkgname}}_${{pkgver}}.tar.gz"
            else:
                source = f"https://github.com/{github_owner}/{github_repo}/releases/download/${{pkgver}}/${{_pkgname}}_${{pkgver}}.tar.gz"
        result["source"] = source
        result["rpkgver"] = rpkgver
        config = configparser.ConfigParser()
        # meta db data in self.descs is not complete, still need to fetch desc for specific rpkgname
        r = requests.get(url, allow_redirects=True)
        if repo == "github":
            tarfilename = f"{github_repo}_{rpkgver}.tar.gz"
            desc_filename = f"{github_repo}/DESCRIPTION"
        else:
            tarfilename = f"{rpkgname}_{rpkgver}.tar.gz"
            desc_filename = f"{rpkgname}/DESCRIPTION"
        if r.status_code == requests.codes.ok:
            with open(tarfilename, "wb") as f:
                f.write(r.content)
        else:
            raise RuntimeError(
                f"Failed to get source tarball {rpkgname}-{rpkgver}.tar.gz due to: {r.reason}")
        with tarfile.open(tarfilename) as f:
            f.extract(desc_filename)
            if self.has_fortran_src(f):
                result["makedepends"] = ["gcc-fortran"]
        with open(desc_filename, "r") as f:
            config.read_string(f"[{rpkgname}]\n" + f.read())
        if clean:
            os.remove(tarfilename)
            os.remove(desc_filename)
            os.removedirs(osp.dirname(desc_filename))
        if "title" in config[rpkgname]:
            result["title"] = config[rpkgname]["title"].replace(
                '\n', ' ').strip()
        if "needscompilation" in config[rpkgname]:
            if config[rpkgname]["needscompilation"] == "yes":
                result["arch"] = "x86_64"
        r_deps = []
        if "imports" in config[rpkgname]:
            r_deps += config[rpkgname]["imports"].split(',')
        if "depends" in config[rpkgname]:
            r_deps += config[rpkgname]["depends"].split(',')
        if "linkingto" in config[rpkgname]:
            r_deps += config[rpkgname]["linkingto"].split(',')
        r_deps = [_.split('(')[0].strip() for _ in r_deps]
        r_deps = list(set(r_deps) - self.exclude_pkgs)
        if '' in r_deps:
            r_deps.remove('')
        result["r_depends"] = sorted(r_deps)
        result["depends"] += [f"r-{_.lower()}" for _ in result["r_depends"]]
        result["depends"] = sorted(result["depends"])
        r_optdeps = []
        if "suggests" in config[rpkgname]:
            r_optdeps += config[rpkgname]["suggests"].strip().split(',')
        if "enhances" in config[rpkgname]:
            r_optdeps += config[rpkgname]["enhances"].strip().split(',')
        r_optdeps = [_.split('(')[0].strip() for _ in r_optdeps]
        if '' in r_optdeps:
            r_optdeps.remove('')
        result["r_optdepends"] = sorted(r_optdeps)
        result["optdepends"] = sorted(
            [f"r-{_.lower()}" for _ in result['r_optdepends']])
        if "systemrequirements" in config[rpkgname]:
            result["systemrequirements"] = config[rpkgname]["systemrequirements"].replace(
                '\n', '').strip()
        # deal with license
        if "LGPL" in config[rpkgname]["license"] or config[rpkgname]["license"] == "GNU Lesser General Public License":
            result["license"] = "LGPL"
        elif "AGPL" in config[rpkgname]["license"] or config[rpkgname]["license"] == "GNU Affero General Public License":
            result["license"] = "AGPL"
        elif "GNU General Public License" in config[rpkgname]["license"] or "GPL" in config[rpkgname]["license"]:
            result["license"] = "GPL"
        elif "Apache" in config[rpkgname]["license"]:
            result["license"] = "Apache"
        elif "BSD" in config[rpkgname]["license"]:
            result["license"] = "BSD"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "Artistic" in config[rpkgname]["license"]:
            result["license"] = "Artistic2.0"
        elif "CC BY" in config[rpkgname]["license"] or config[rpkgname]["license"] == "Creative Commons Attribution 4.0 International License":
            result["license"] = "CCPL:by-nc-sa"
        elif config[rpkgname]["license"] in ["Mozilla Public License 1.1",
                                             "MPL",
                                             "MPL-1.1"]:
            result["license"] = "MPL"
        elif config[rpkgname]["license"] in [
            "Mozilla Public License 2.0",
            "Mozilla Public License Version 2.0",
            "MPL (>= 2)",
            "MPL (== 2.0)",
            "MPL (>= 2.0)",
            "MPL-2.0",
            "MPL-2.0 | file LICENSE",
            "MPL (>= 2) | file LICENSE"
        ]:
            result["license"] = "MPL2"
        elif "CPL" in config[rpkgname]["license"] or config[rpkgname]["license"] == "Common Public License Version 1.0":
            result["license"] = "CPL"
        elif "MIT" in config[rpkgname]["license"]:
            result["license"] = "MIT"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "EPL" in config[rpkgname]["license"]:
            result["license"] = "EPL"
        elif "CeCILL" in config[rpkgname]["license"]:
            result["license"] = "CeCILL"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "EUPL" in config[rpkgname]["license"]:
            result["license"] = "EUPL"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "ACM" in config[rpkgname]["license"]:
            result["license"] = "ACM"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "BSL" in config[rpkgname]["license"]:
            result["license"] = "BSL"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "CC0" in config[rpkgname]["license"]:
            result["license"] = "CC0"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "Lucent Public License" in config[rpkgname]["license"]:
            result["license"] = "Lucent Public License"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        elif "Unlimited" in config[rpkgname]["license"]:
            result["license"] = "Unlimited"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"
        else:
            result["license"] = "custom"
            if "file LICENSE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENSE"
            if "file LICENCE" in config[rpkgname]["license"]:
                result["license_filename"] = "LICENCE"

        return result

    def write_lilac_yaml(self, filename, desc_dict):
        url = desc_dict["project_url"].replace(
            '${_pkgname}', desc_dict["rpkgname"])
        yaml_dict = {
            "maintainers": [
                {"github": desc_dict["maintainer_github"]}
            ],
            "build_prefix": "extra-x86_64",
            "update_on": [
                {
                    "source": "rpkgs",
                    "pkgname": desc_dict["rpkgname"],
                    "repo": desc_dict["repo"]
                },
                {
                    "alias": "r"
                }
            ]
        }
        if desc_dict["repo"] == "github":
            yaml_dict["update_on"] = [{
                "source": "github",
                "github": f'{desc_dict["github_owner"]}/{desc_dict["rpkgname"]}',
                "use_latest_release": True}]
        repo_depends = desc_dict["depends"]
        repo_depends.remove("r")
        if repo_depends:
            yaml_dict["repo_depends"] = repo_depends
        with open(filename, "w", newline='\n') as f:
            yaml.safe_dump(yaml_dict, f)
        # run prettier to make pretty yaml
        os.system(f'prettier -w {filename}')
        # add build_script
        with open(filename, 'r') as f:  
            lines = f.readlines() 
            index = 0  
            for i, line in enumerate(lines):  
                if 'update_on' in line:  
                    index = i  
                    break  
            lines.insert(index, "pre_build_script: |\n  for line in edit_file('PKGBUILD'):\n    if line.startswith('_pkgver='):\n      line = f'_pkgver={_G.newver}'\n    print(line)\n  update_pkgver_and_pkgrel(_G.newver.replace(':', '.').replace('-', '.'))\npost_build_script: |\n  git_pkgbuild_commit()\n")  
            with open(filename, 'w') as f:  
                f.writelines(lines)
                
    def write_pkgbuild(self, filename, desc_dict):
        """
        generate the PKGBUILD file based on information parsed from DESCRIPTION file
        args:
            filename: the PKGBUILD file path
            desc_dict: dict contains information parsed from DESCRIPTION file
        """
        depends = '\n'.join([
            'depends=(',
            '\n'.join(['  ' + _ for _ in desc_dict["depends"]]),
            ')'
        ])
        optdepends = None
        if desc_dict["optdepends"]:
            optdepends = '\n'.join([
                'optdepends=(',
                '\n'.join(['  ' + _ for _ in desc_dict["optdepends"]]),
                ')'
            ])
        makedepends = None
        if desc_dict["makedepends"]:
            makedepends = '\n'.join([
                'makedepends=(',
                '\n'.join(['  ' + _ for _ in desc_dict["makedepends"]]),
                ')'
            ])
        build_func = '\n'.join([
            'build() {',
            '  R CMD INSTALL ${_pkgname}_${_pkgver}.tar.gz -l "${srcdir}"',
            '}'
        ])
        if desc_dict["repo"] == "github":
            build_func = '\n'.join([
                'build() {',
                '  R CMD INSTALL ${_pkgname}_${pkgver}.tar.gz -l "${srcdir}"',
                '}'
            ])

        if desc_dict["license_filename"]:
            package_func = '\n'.join([
                'package() {',
                '  install -dm0755 "${pkgdir}/usr/lib/R/library"',
                '  cp -a --no-preserve=ownership "${_pkgname}" "${pkgdir}/usr/lib/R/library"',
                f'  install -Dm644 "${{_pkgname}}/{desc_dict["license_filename"]}" -t "${{pkgdir}}/usr/share/licenses/${{pkgname}}"',
                '}'
            ])
        else:
            package_func = '\n'.join([
                'package() {',
                '  install -dm0755 "${pkgdir}/usr/lib/R/library"',
                '  cp -a --no-preserve=ownership "${_pkgname}" "${pkgdir}/usr/lib/R/library"',
                '}'
            ])
        # constuct each line of PKGBUILD file
        systemrequirements_line = None
        if desc_dict["systemrequirements"]:
            systemrequirements_line = f'# system requirements: {desc_dict["systemrequirements"]}'
        maintainer_line = f'# Maintainer: {desc_dict["maintainer"]} <{desc_dict["email"]}>\n'
        _pkgname_line = f'_pkgname={desc_dict["rpkgname"]}'
        _pkgver_line = f'_pkgver={desc_dict["rpkgver"]}'
        pkgname_line = 'pkgname=r-${_pkgname,,}'
        pkgver_line = 'pkgver=${_pkgver//[:-]/.}'
        pkgrel_line = 'pkgrel=1'
        pkgdesc_line = f"pkgdesc='{desc_dict['title']}'"
        if "'" in desc_dict["title"]:
            pkgdesc_line = f'pkgdesc="{desc_dict["title"]}"'
        arch_line = f"arch=('{desc_dict['arch']}')"
        url_line = f'url="{desc_dict["project_url"]}"'
        license_line = f"license=('{desc_dict['license']}')"
        depends_line = depends
        optdepends_line = optdepends
        makedepends_line = makedepends
        source_line = f'source=("{desc_dict["source"]}")'
        checksums_line = "sha256sums=('a')\n"
        build_line = build_func + '\n'
        package_line = package_func
        end_line = '# vim:set ts=2 sw=2 et:\n'
        # deal with github
        if desc_dict["repo"] == "github":
            _pkgver_line = None
            pkgver_line = f'pkgver={desc_dict["rpkgver"].replace(":", "").replace("-", "")}'

        pkgbuild_lines = []
        if systemrequirements_line:
            pkgbuild_lines.append(systemrequirements_line)
        pkgbuild_lines += [
            maintainer_line,
            _pkgname_line
        ]
        if desc_dict["repo"] != "github":
            pkgbuild_lines.append(_pkgver_line)
        pkgbuild_lines += [
            pkgname_line,
            pkgver_line,
            pkgrel_line,
            pkgdesc_line,
            arch_line,
            url_line,
            license_line,
            depends_line
        ]
        if optdepends_line:
            pkgbuild_lines.append(optdepends_line)
        if makedepends:
            pkgbuild_lines.append(makedepends_line)
        pkgbuild_lines += [
            source_line,
            checksums_line,
            build_line,
            package_line,
            end_line
        ]

        pkgbuild_content = '\n'.join(pkgbuild_lines)
        with open(filename, 'w', newline='\n') as f:
            f.write(pkgbuild_content)

    def generate_pkgbuild(
        self,
        rpkgname,
        maintainer_github,
        skip=False,
        recursive=False,
        maintainer=None,
        email=None,
        verbose=False,
        updpkgsums=False,
        repo="cran",
        clean=True,
        destdir='.'
    ):
        if repo == "github":
            pkgname = f"r-{rpkgname.strip('/').split('/')[-1].lower()}"
        else:
            pkgname = f"r-{rpkgname.lower()}"
        if verbose:
            print(f"generating PKGBUILD for pkg: {rpkgname}")
        pkgbuild_filename = f"{osp.join(destdir, pkgname)}/PKGBUILD"
        lilac_yaml_filename = f"{osp.join(destdir, pkgname)}/lilac.yaml"
        lilac_py_filename = f"{osp.join(destdir, pkgname)}/lilac.py"
        if skip and osp.exists(pkgbuild_filename):
            if verbose:
                print(
                    f"skip PKGBUILD generation of pkg: {pkgname} as it exists")
            return
        desc_dict = self.parse_description(rpkgname, repo, clean)
        desc_dict["maintainer"] = maintainer
        desc_dict["email"] = email
        desc_dict["maintainer_github"] = maintainer_github

        os.makedirs(osp.join(destdir, pkgname), exist_ok=True)
        self.write_pkgbuild(pkgbuild_filename, desc_dict)
        self.write_lilac_yaml(lilac_yaml_filename, desc_dict)
        if updpkgsums:
            if verbose:
                print("updating source checksums")
            os.system(f"updpkgsums {pkgbuild_filename}")
        if recursive:
            for rpkgname_dep in desc_dict["r_depends"]:
                # for pkg dep not from cran repo, check if it's in CRAN
                # we can not know if the pkg in cran in recursive mode
                # so we check it here
                # for pkg from github, we assume that it's deps are not from github anymore
                if self.isInCran(rpkgname_dep):
                    repo = "cran"
                else:
                    repo = "bioconductor"
                self.generate_pkgbuild(
                    rpkgname_dep,
                    maintainer_github,
                    skip=skip,
                    recursive=recursive,
                    maintainer=maintainer,
                    email=email,
                    verbose=verbose,
                    updpkgsums=updpkgsums,
                    repo=repo,
                    destdir=destdir,
                    clean=clean
                )
