import hashlib
import urllib.parse

from pip._internal.req.req_file import parse_requirements

from pdm.models.markers import Marker
from pdm.models.requirements import parse_requirement
from pdm.utils import get_finder


def _requirement_to_str_lowercase_name(requirement):
    """Formats a packaging.requirements.Requirement with a lowercase name."""
    parts = [requirement.name.lower()]

    if requirement.extras:
        parts.append("[{0}]".format(",".join(sorted(requirement.extras))))

    if requirement.specifier:
        parts.append(str(requirement.specifier))

    if requirement.url:
        parts.append("@ {0}".format(requirement.url))

    if requirement.marker:
        parts.append("; {0}".format(requirement.marker))

    return "".join(parts)


def requirement_from_ireq(ireq):
    """Formats an `InstallRequirement` instance as a
    `pdm.models.requirement.Requirement`.

    Generic formatter for pretty printing InstallRequirements to the terminal
    in a less verbose way than using its `__str__` method.

    :param :class:`InstallRequirement` ireq: A pip **InstallRequirement** instance.
    :return: A formatted string for prettyprinting
    :rtype: str
    """
    if ireq.editable:
        line = "{}".format(ireq.link)
    else:
        line = _requirement_to_str_lowercase_name(ireq.req)

    if str(ireq.req.marker) != str(ireq.markers):
        if not ireq.req.marker:
            line = "{}; {}".format(line, ireq.markers)
        else:
            name, markers = line.split(";", 1)
            markers = Marker(markers) & ireq.markers
            line = "{}; {}".format(name, markers)

    return parse_requirement(line, ireq.editable)


def parse_requirement_file(filename):
    finder = get_finder([])
    ireqs = list(parse_requirements(filename, finder.session, finder))
    return ireqs, finder


def check_fingerprint(project, filename):
    import tomlkit

    with open(filename, encoding="utf-8") as fp:
        try:
            tomlkit.parse(fp.read())
        except ValueError:
            # the file should be a requirements.txt if it not a TOML document.
            return True
        else:
            return False


def convert_url_to_source(url, name=None):
    if not name:
        name = hashlib.sha1(url.encode("utf-8")).hexdigest()[:6]
    return {"name": name, "url": url, "verify_ssl": url.startswith("https://")}


def convert(project, filename):
    ireqs, finder = parse_requirement_file(str(filename))
    reqs = [requirement_from_ireq(ireq) for ireq in ireqs]

    data = {"dependencies": dict(req.as_req_dict() for req in reqs)}
    if finder.index_urls:
        sources = [convert_url_to_source(finder.index_urls[0], "pypi")]
        sources.extend(convert_url_to_source(url) for url in finder.index_urls[1:])
        data["source"] = sources

    return data


def export(project, candidates, options):
    lines = []
    for candidate in candidates:
        req = candidate.req.as_line()
        lines.append(req)
        if options.hashes and candidate.hashes:
            for item in candidate.hashes.values():
                lines.append(f" \\\n    --hash={item}")
        lines.append("\n")
    sources = project.tool_settings.get("source", [])
    for source in sources:
        url = source["url"]
        prefix = "--index-url" if source["name"] == "pypi" else "--extra-index-url"
        lines.append(f"{prefix} {url}\n")
        if not source["verify_ssl"]:
            host = urllib.parse.urlparse(url).hostname
            lines.append(f"--trusted-host {host}\n")
    return "".join(lines)
