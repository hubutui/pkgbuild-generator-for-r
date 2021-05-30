#!/usr/bin/env python3
import argparse

from PKGBUILDGenerator.PKGBUILDGenerator import PKGBUILDGenerator


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpkgnames", type=str, nargs='+',
                        help="r pkgnames in CRAN or Bioconductor")
    parser.add_argument("--repo", type=str, choices=["cran", "bioconductor", "github"], default="cran",
                        help="repo to use, default: cran")
    parser.add_argument("--destdir", default='.',
                        help="destdir, default: .")
    parser.add_argument("--maintainer", type=str,
                        help="maintainer in PKGBUILD")
    parser.add_argument("--email", type=str,
                        help="email of maintainer in PKGBUILD")
    parser.add_argument("--clean", action="store_true",
                        help="clean temporaly files")
    parser.add_argument("--recursive", action="store_true",
                        help="create also the PKGBUILD for deps")
    parser.add_argument("--verbose", action="store_true",
                        help="be verbose")
    parser.add_argument("--skip", action="store_true",
                        help="skip PKGBUILD generator if the PKGBUILD exists")
    parser.add_argument("--updpkgsums", action="store_true",
                        help="run updatepkgsums to update source checksums")
    parser.add_argument("--cran-mirror", type=str, default="https://mirrors.ustc.edu.cn/CRAN",
                        help="CRAN mirror, default: https://mirrors.ustc.edu.cn/CRAN")
    parser.add_argument("--bioconductor-mirror", type=str, default="https://mirrors.ustc.edu.cn/bioc/",
                        help="Bioconductor mirror, default: https://mirrors.ustc.edu.cn/bioc/")
    parser.add_argument("--maintainer-github", type=str,
                        help="github username of PKGBUILD maintainer, only used in `lilac.yaml`")

    return parser.parse_args()


if __name__ == '__main__':
    args = get_args()
    gen = PKGBUILDGenerator(
        cran_mirror=args.cran_mirror,
        bioconductor_mirror=args.bioconductor_mirror
    )
    for rpkgname in args.rpkgnames:
        gen.generate_pkgbuild(
            rpkgname=rpkgname,
            maintainer_github=args.maintainer_github,
            maintainer=args.maintainer,
            email=args.email,
            recursive=args.recursive,
            verbose=args.verbose,
            updpkgsums=args.updpkgsums,
            repo=args.repo,
            skip=args.skip,
            destdir=args.destdir,
            clean=args.clean
        )
    print("Done")
