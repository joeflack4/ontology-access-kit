import json
import logging
import re
import unittest
from typing import Optional

import yaml
from click.testing import CliRunner

from oaklib.cli import main
from oaklib.datamodels.vocabulary import IN_TAXON
from tests import (
    ATOM,
    CELLULAR_COMPONENT,
    CHEBI_NUCLEUS,
    IMBO,
    INPUT_DIR,
    INTRACELLULAR,
    NUCLEAR_ENVELOPE,
    NUCLEAR_MEMBRANE,
    NUCLEATED,
    NUCLEUS,
    OUTPUT_DIR,
    SHAPE,
    VACUOLE,
)

TEST_ONT = INPUT_DIR / "go-nucleus.obo"
TEST_OWL_RDF = INPUT_DIR / "go-nucleus.owl.ttl"
TEST_DB = INPUT_DIR / "go-nucleus.db"
BAD_ONTOLOGY_DB = INPUT_DIR / "bad-ontology.db"
TEST_OUT = str(OUTPUT_DIR / "tmp")
TEST_OUT_OBO = str(OUTPUT_DIR / "tmp.obo")
TEST_OUT2 = str(OUTPUT_DIR / "tmp-v2")
TEST_OBO = INPUT_DIR / "unreciprocated-mapping-test.obo"
TEST_SSSOM_MAPPING = INPUT_DIR / "unreciprocated-mapping-test.sssom.tsv"


class TestCommandLineInterface(unittest.TestCase):
    """
    Tests all command-line subcommands
    """

    def setUp(self) -> None:
        runner = CliRunner(mix_stderr=False)
        self.runner = runner

    def _out(self, path: Optional[str] = TEST_OUT) -> str:
        with open(path) as f:
            return "".join(f.readlines())

    def test_main_help(self):
        result = self.runner.invoke(main, ["--help"])
        out = result.stdout
        result.stderr
        self.assertIn("search", out)
        self.assertIn("subset", out)
        self.assertIn("validate", out)
        self.assertEqual(0, result.exit_code)

    def test_info(self):
        for input_arg in [TEST_ONT, f"sqlite:{TEST_DB}", TEST_OWL_RDF]:
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "info", NUCLEUS, "-o", TEST_OUT, "-D", "x,d"]
            )
            result.stdout
            result.stderr
            self.assertEqual(0, result.exit_code)
            with open(TEST_OUT) as file:
                contents = "\n".join(file.readlines())
                self.assertIn(NUCLEUS, contents)
                self.assertIn("Wikipedia:Cell_nucleus", contents)
                self.assertIn("A membrane-bounded organelle", contents)
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "info", NUCLEUS, "-o", TEST_OUT, "-D", "x"]
            )
            result.stdout
            result.stderr
            self.assertEqual(0, result.exit_code)
            with open(TEST_OUT) as file:
                contents = "\n".join(file.readlines())
                self.assertIn(NUCLEUS, contents)
                self.assertIn("Wikipedia:Cell_nucleus", contents)
                self.assertNotIn("A membrane-bounded organelle", contents)

    def test_labels(self):
        for input_arg in [f"sqlite:{TEST_DB}"]:
            result = self.runner.invoke(main, ["-i", str(input_arg), "labels", ".all"])
            assert "cytoplasm" in result.stdout
            assert "IAO:0000078" in result.stdout
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "labels", ".all", "--if-absent", "present-only"]
            )
            assert "cytoplasm" in result.stdout
            assert "IAO:0000078" not in result.stdout
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "labels", ".all", "--if-absent", "absent-only"]
            )
            assert "cytoplasm" not in result.stdout
            assert "IAO:0000078" in result.stdout

    def test_definitions(self):
        for input_arg in [f"sqlite:{TEST_DB}"]:
            result = self.runner.invoke(main, ["-i", str(input_arg), "definitions", ".all"])
            print(result.stdout)
            assert "cytoplasm" in result.stdout
            assert "IAO:0000078" in result.stdout
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "definitions", ".all", "--if-absent", "present-only"]
            )
            assert "cytoplasm" in result.stdout
            assert "IAO:0000078" not in result.stdout
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "definitions", ".all", "--if-absent", "absent-only"]
            )
            assert "cytoplasm" not in result.stdout
            assert "IAO:0000078" in result.stdout

    # OBOGRAPH

    def test_obograph_local(self):
        for input_arg in [str(TEST_ONT), f"sqlite:{TEST_DB}", str(TEST_OWL_RDF)]:
            logging.info(f"INPUT={input_arg}")
            self.runner.invoke(main, ["-i", input_arg, "ancestors", NUCLEUS, "-o", TEST_OUT])
            out = self._out()
            assert "GO:0043226" in out
            self.runner.invoke(
                main, ["-i", input_arg, "ancestors", "-p", "i", "plasma membrane", "-o", TEST_OUT]
            )
            out = self._out()
            assert "GO:0016020" in out
            assert "GO:0043226" not in out
            self.runner.invoke(
                main, ["-i", input_arg, "descendants", "-p", "i", "GO:0016020", "-o", TEST_OUT]
            )
            out = self._out()
            # TODO:
            # assert 'GO:0016020 ! membrane' not in out
            assert "GO:0043226" not in out
            # test fetching ancestor graph and saving as obo
            self.runner.invoke(
                main,
                [
                    "-i",
                    input_arg,
                    "descendants",
                    "-p",
                    "i,p",
                    "GO:0016020",
                    "-O",
                    "obo",
                    "-o",
                    TEST_OUT_OBO,
                ],
            )
            self.runner.invoke(main, ["-i", TEST_OUT_OBO, "info", ".all", "-o", TEST_OUT])
            out = self._out(TEST_OUT)
            logging.info(out)
            assert "GO:0016020" in out
            assert "GO:0031965" in out
            assert "subClassOf" not in out
            assert "BFO" not in out

    def test_gap_fill(self):
        result = self.runner.invoke(
            main,
            [
                "-i",
                str(TEST_DB),
                "viz",
                "--gap-fill",
                "-p",
                f"i,p,{IN_TAXON}",
                NUCLEUS,
                VACUOLE,
                CELLULAR_COMPONENT,
                "-O",
                "json",
                "-o",
                TEST_OUT,
            ],
        )
        result.stdout
        result.stderr
        self.assertEqual(0, result.exit_code)
        contents = self._out()
        self.assertIn(NUCLEUS, contents)
        self.assertIn(VACUOLE, contents)
        self.assertIn(CELLULAR_COMPONENT, contents)
        # parse json to check it conforms
        with open(TEST_OUT) as f:
            g = json.load(f)
            nodes = g["nodes"]
            g["edges"]
            [nucleus_node] = [n for n in nodes if n["id"] == NUCLEUS]
            self.assertEqual(nucleus_node["lbl"], "nucleus")

    def test_roots_and_leafs(self):
        for input_arg in [str(TEST_ONT), f"sqlite:{TEST_DB}", str(TEST_OWL_RDF)]:
            result = self.runner.invoke(main, ["-i", input_arg, "roots", "-p", "i"])
            out = result.stdout
            assert "CHEBI:36342" in out
            result = self.runner.invoke(main, ["-i", input_arg, "leafs", "-p", "i"])
            out = result.stdout
            assert NUCLEAR_ENVELOPE in out
            result = self.runner.invoke(main, ["-i", input_arg, "singletons", "-p", "i"])
            out = result.stdout
            print(out)
            assert NUCLEAR_ENVELOPE not in out

    # MAPPINGS

    def test_mappings_local(self):
        result = self.runner.invoke(
            main, ["-i", str(TEST_ONT), "mappings", "GO:0016740", "-o", TEST_OUT, "-O", "csv"]
        )
        out = result.stdout
        self.assertEqual(0, result.exit_code)
        out = self._out()
        self.assertIn("EC:2.-.-.-", out)
        self.assertIn("Reactome:R-HSA-1483089", out)

    # TAXON

    def test_taxon_constraints_local(self):
        for input_arg in [TEST_ONT, f"sqlite:{TEST_DB}", TEST_OWL_RDF]:
            result = self.runner.invoke(
                main, ["-i", str(input_arg), "taxon-constraints", NUCLEUS, "-o", TEST_OUT]
            )
            result.stdout
            result.stderr
            self.assertEqual(0, result.exit_code)
            contents = self._out()
            self.assertIn("Eukaryota", contents)

    # SEARCH

    def test_search_help(self):
        result = self.runner.invoke(main, ["search", "--help"])
        out = result.stdout
        result.stderr
        self.assertEqual(0, result.exit_code)
        self.assertIn("Usage:", out)
        self.assertIn("Example:", out)

    def test_search_local(self):
        for input_arg in [str(TEST_ONT), f"sqlite:{TEST_DB}", TEST_OWL_RDF]:
            logging.info(f"INPUT={input_arg}")
            result = self.runner.invoke(
                main, ["-i", input_arg, "search", "l~nucl", "-o", str(TEST_OUT)]
            )
            out = self._out()
            err = result.stderr
            if result.exit_code != 0:
                logging.info(f"INPUT: {input_arg} code = {result.exit_code}")
                logging.info(f"OUTPUT={out}")
                logging.info(f"ERR={err}")
            logging.info(f"OUTPUT={out}")
            logging.info(f"ERR={err}")
            self.assertEqual(0, result.exit_code)
            self.assertIn(NUCLEUS, out)
            self.assertIn("nucleus", out)
            self.assertEqual("", err)

    def test_search_local_advanced(self):
        """
        Tests boolean combinations of search results
        """
        # tuples of (terms, complete, expected, excluded)
        search_tests = [
            (["nucleus"], True, [NUCLEUS], []),
            (["t^nucleus"], True, [NUCLEUS], []),
            (["t/^n.....s$"], True, [NUCLEUS], []),
            (["t~nucleus"], True, [NUCLEUS, CHEBI_NUCLEUS], []),
            # TODO: empty files
            # (["l=protoplasm"], True, [], []),
            (["t=protoplasm"], True, [INTRACELLULAR], []),
            ([".=protoplasm"], True, [INTRACELLULAR], []),
            (
                # terms that start with "nucl" are in PATO, with one exception
                ["t/^nucl", ".and", "i/^PATO", ".not", "PATO:0001404"],
                True,
                [NUCLEATED],
                [TEST_OWL_RDF],
            ),
            (
                # is-a descendants of nucleus
                [".desc//p=i,p", "nucleus"],
                True,
                [NUCLEUS, NUCLEAR_ENVELOPE, NUCLEAR_MEMBRANE],
                [TEST_OWL_RDF],
            ),
            (
                # is-a ancestors of nucleus that are not a particular term
                [".anc//p=i", "nucleus", ".not", ".anc//p=i", IMBO],
                True,
                [NUCLEUS],
                [TEST_OWL_RDF],
            ),
            (
                # is-a/part-of descendants of nucleus are not found in a label search for "membrane"
                [".desc//p=i,p", "nucleus", ".not", "l~membrane"],
                True,
                [NUCLEUS, NUCLEAR_ENVELOPE],
                [TEST_OWL_RDF],
            ),
            (
                # filter query
                [
                    ".anc//p=i",
                    "nucleus",
                    ".filter",
                    "[x for x in terms if not impl.definition(x)]",
                ],
                True,
                ["CARO:0000000", "CARO:0030000"],
                [TEST_OWL_RDF],
            ),
            (
                # all terms
                [".all"],
                False,
                [NUCLEUS, NUCLEAR_ENVELOPE],
                [TEST_OWL_RDF],
            ),
            # (
            #    # no terms
            #    [".all", ".not", ".all"],
            #    True,
            #    [],
            #    [TEST_OWL_RDF],
            # ),
        ]
        inputs = [TEST_ONT, f"sqlite:{TEST_DB}", TEST_OWL_RDF]
        for input_arg in inputs:
            logging.info(f"INPUT={input_arg}")
            for t in search_tests:
                logging.info(f"{input_arg} // {t}")
                terms, complete, expected, excluded = t
                if input_arg in excluded:
                    logging.info(f"Skipping {terms} as {input_arg} in Excluded: {excluded}")
                    continue
                result = self.runner.invoke(
                    main, ["-i", str(input_arg), "search"] + terms + ["-o", str(TEST_OUT)]
                )
                out = self._out()
                err = result.stderr
                if result.exit_code != 0:
                    logging.error(f"INPUT: {input_arg} code = {result.exit_code}")
                    logging.error(f"OUTPUT={out}")
                    logging.error(f"ERR={err}")
                self.assertEqual(0, result.exit_code)
                logging.info(f"OUTPUT={out}")
                logging.info(f"ERR={err}")
                self.assertEqual(0, result.exit_code)
                self.assertEqual("", err)
                lines = out.split("\n")
                curies = []
                for line in lines:
                    m = re.match(r"(\S+)\s+!", line)
                    if m:
                        curies.append(m.group(1))
                logging.info(f"SEARCH: {terms} => {curies} // {input_arg}")
                if complete:
                    self.assertCountEqual(expected, set(curies))
                else:
                    for e in expected:
                        self.assertIn(e, curies)

    def test_search_pronto_obolibrary(self):
        to_out = ["-o", str(TEST_OUT)]
        result = self.runner.invoke(
            main, ["-i", "prontolib:pato.obo", "search", "t~shape"] + to_out
        )
        out = self._out()
        err = result.stderr
        self.assertEqual(0, result.exit_code)
        self.assertIn(SHAPE, out)
        self.assertIn("PATO:0002021", out)  # conical - matches a synonym
        self.assertEqual("", err)
        result = self.runner.invoke(
            main, ["-i", "prontolib:pato.obo", "search", "l=shape"] + to_out
        )
        out = self._out()
        err = result.stderr
        self.assertEqual(0, result.exit_code)
        self.assertIn(SHAPE, out)
        self.assertNotIn("PATO:0002021", out)  # conical - matches a synonym
        self.assertEqual("", err)
        result = self.runner.invoke(main, ["-i", "prontolib:pato.obo", "search", "shape"] + to_out)
        out = self._out()
        err = result.stderr
        self.assertEqual(0, result.exit_code)
        self.assertIn(SHAPE, out)
        self.assertNotIn("PATO:0002021", out)  # conical - matches a synonym
        self.assertEqual("", err)

    # VALIDATE

    def test_validate_help(self):
        result = self.runner.invoke(main, ["validate", "--help"])
        result.stdout
        result.stderr
        self.assertEqual(0, result.exit_code)

    def test_validate_bad_ontology(self):
        for input_arg in [f"sqlite:{BAD_ONTOLOGY_DB}"]:
            logging.info(f"INPUT={input_arg}")
            result = self.runner.invoke(main, ["-i", input_arg, "validate"])
            out = result.stdout
            err = result.stderr
            logging.info(f"ERR={err}")
            self.assertEqual(0, result.exit_code)
            self.assertIn("EXAMPLE:1", out)
            self.assertIn("EXAMPLE:2", out)
            self.assertEqual("", err)

    def test_check_definitions(self):
        for input_arg in [TEST_ONT, f"sqlite:{TEST_DB}"]:
            logging.info(f"INPUT={input_arg}")
            result = self.runner.invoke(main, ["-i", input_arg, "check-definitions"])
            out = result.stdout
            err = result.stderr
            logging.info(f"ERR={err}")
            self.assertEqual(0, result.exit_code)
            self.assertIn(ATOM, out)
            self.assertEqual("", err)

    # LEXICAL

    def test_lexmatch_owl(self):
        outfile = f"{OUTPUT_DIR}/matcher-test-cli.owl.sssom.tsv"
        result = self.runner.invoke(
            main,
            [
                "-i",
                f"pronto:{INPUT_DIR}/matcher-test.owl",
                "lexmatch",
                "-R",
                f"{INPUT_DIR}/matcher_rules.yaml",
                "-o",
                outfile,
            ],
        )
        result.stdout
        err = result.stderr
        self.assertEqual(0, result.exit_code)
        with open(outfile) as stream:
            contents = "\n".join(stream.readlines())
            self.assertIn("skos:closeMatch", contents)
            self.assertIn("skos:exactMatch", contents)
        self.assertEqual("", err)

    def test_lexmatch_sqlite(self):
        outfile = f"{OUTPUT_DIR}/matcher-test-cli.db.sssom.tsv"
        result = self.runner.invoke(
            main,
            [
                "-i",
                f"sqlite:{INPUT_DIR}/matcher-test.db",
                "lexmatch",
                "-R",
                f"{INPUT_DIR}/matcher_rules.yaml",
                "-o",
                outfile,
            ],
        )
        result.stdout
        err = result.stderr
        self.assertEqual("", err)
        self.assertEqual(0, result.exit_code)
        with open(outfile) as stream:
            contents = "\n".join(stream.readlines())
            self.assertIn("skos:closeMatch", contents)
            self.assertIn("skos:exactMatch", contents)
            self.assertIn("x:bone_element", contents)
            self.assertIn("bone tissue", contents)

    def test_similarity(self):
        result = self.runner.invoke(
            main,
            ["-i", TEST_DB, "similarity", NUCLEAR_MEMBRANE, VACUOLE, "-p", "i,p", "-o", TEST_OUT],
        )
        # out = result.stdout
        result.stderr
        self.assertEqual(0, result.exit_code)
        out = self._out()
        self.assertIn(IMBO, out)
        with open(TEST_OUT) as f:
            obj = yaml.safe_load(f)
            # logging.info(obj)
            self.assertEqual(obj["subject_id"], NUCLEAR_MEMBRANE)
            self.assertEqual(obj["object_id"], VACUOLE)
            self.assertEqual(obj["ancestor_id"], IMBO)
            self.assertGreater(obj["jaccard_similarity"], 0.5)
            self.assertGreater(obj["ancestor_information_content"], 3.0)

    def test_diff_via_mappings(self):
        outfile = f"{OUTPUT_DIR}/diff-mapping-test-cli.sssom"
        result = self.runner.invoke(
            main,
            [
                "-i",
                TEST_OBO,
                "diff-via-mappings",
                "--mapping-input",
                TEST_SSSOM_MAPPING,
                "--intra",
                "-S",
                "X",
                "-S",
                "Y",
                "-o",
                outfile,
            ],
        )
        result.stderr
        self.assertEqual(0, result.exit_code)
        with open(outfile) as f:
            docs = yaml.load_all(f, yaml.FullLoader)
            for doc in docs:
                self.assertTrue(type(doc), dict)
