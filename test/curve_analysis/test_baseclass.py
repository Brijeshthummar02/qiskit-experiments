# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# pylint: disable=invalid-name

"""Test curve fitting base class."""
from test.base import QiskitExperimentsTestCase
from test.fake_experiment import FakeExperiment
from typing import List

import numpy as np
from qiskit.qobj.utils import MeasLevel
from uncertainties import correlated_values

from qiskit_experiments.curve_analysis import CurveAnalysis, fit_function
from qiskit_experiments.curve_analysis.curve_data import (
    SeriesDef,
    FitData,
    ParameterRepr,
    FitOptions,
)
from qiskit_experiments.data_processing import DataProcessor, Probability
from qiskit_experiments.exceptions import AnalysisError
from qiskit_experiments.framework import ExperimentData


def simulate_output_data(func, xvals, param_dict, **metadata):
    """Generate arbitrary fit data."""
    __shots = 100000

    expected_probs = func(xvals, **param_dict)
    counts = np.asarray(expected_probs * __shots, dtype=int)

    data = [
        {
            "counts": {"0": __shots - count, "1": count},
            "metadata": dict(xval=xi, qubits=(0,), experiment_type="fake_experiment", **metadata),
        }
        for xi, count in zip(xvals, counts)
    ]

    expdata = ExperimentData(experiment=FakeExperiment())
    for datum in data:
        expdata.add_data(datum)

    expdata.metadata["meas_level"] = MeasLevel.CLASSIFIED

    return expdata


def create_new_analysis(series: List[SeriesDef], fixed_params: List[str] = None) -> CurveAnalysis:
    """A helper function to create a mock analysis class instance."""

    class TestAnalysis(CurveAnalysis):
        """A mock analysis class to test."""

        __series__ = series

        @classmethod
        def _default_options(cls):
            opts = super()._default_options()
            if fixed_params:
                opts.fixed_parameters = {p: None for p in fixed_params}

            return opts

    return TestAnalysis()


class TestCurveAnalysisUnit(QiskitExperimentsTestCase):
    """Unittest for curve fit analysis."""

    class TestAnalysis(CurveAnalysis):
        """Fake analysis class for unittest."""

        __series__ = [
            SeriesDef(
                name="curve1",
                fit_func=lambda x, par0, par1, par2, par3, par4: fit_function.exponential_decay(
                    x, amp=par0, lamb=par1, baseline=par4
                ),
                filter_kwargs={"op1": 1, "op2": True},
                model_description=r"p_0 * \exp(p_1 x) + p4",
            ),
            SeriesDef(
                name="curve2",
                fit_func=lambda x, par0, par1, par2, par3, par4: fit_function.exponential_decay(
                    x, amp=par0, lamb=par2, baseline=par4
                ),
                filter_kwargs={"op1": 2, "op2": True},
                model_description=r"p_0 * \exp(p_2 x) + p4",
            ),
            SeriesDef(
                name="curve3",
                fit_func=lambda x, par0, par1, par2, par3, par4: fit_function.exponential_decay(
                    x, amp=par0, lamb=par3, baseline=par4
                ),
                filter_kwargs={"op1": 3, "op2": True},
                model_description=r"p_0 * \exp(p_3 x) + p4",
            ),
        ]

    def test_parsed_fit_params(self):
        """Test parsed fit params."""
        analysis = self.TestAnalysis()
        self.assertSetEqual(set(analysis.parameters), {"par0", "par1", "par2", "par3", "par4"})

    def test_cannot_create_invalid_series_fit(self):
        """Test we cannot create invalid analysis instance."""
        invalid_series = [
            SeriesDef(
                name="fit1",
                fit_func=lambda x, par0: fit_function.exponential_decay(x, amp=par0),
            ),
            SeriesDef(
                name="fit2",
                fit_func=lambda x, par1: fit_function.exponential_decay(x, amp=par1),
            ),
        ]

        instance = create_new_analysis(series=invalid_series)
        with self.assertRaises(AnalysisError):
            # pylint: disable=pointless-statement
            instance.parameters  # fit1 has param par0 while fit2 has par1

    def test_data_extraction(self):
        """Test data extraction method."""
        xvalues = np.linspace(1.0, 5.0, 10)

        analysis = self.TestAnalysis()
        analysis.set_options(data_processor=DataProcessor("counts", [Probability("1")]))

        # data to analyze
        test_data0 = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=xvalues,
            param_dict={"amp": 1.0},
            op1=1,
            op2=True,
        )

        curve_data = analysis._run_data_processing(
            raw_data=test_data0.data(),
            series=analysis.__series__,
        )

        # check x values
        ref_x = xvalues
        np.testing.assert_array_almost_equal(curve_data.x, ref_x)

        # check y values
        ref_y = fit_function.exponential_decay(xvalues, amp=1.0)
        np.testing.assert_array_almost_equal(curve_data.y, ref_y, decimal=3)

        # check data allocation
        ref_alloc = np.zeros(10, dtype=int)
        self.assertListEqual(list(curve_data.data_allocation), list(ref_alloc))

    def test_data_extraction_with_subset(self):
        """Test data extraction method with multiple series."""
        xvalues = np.linspace(1.0, 5.0, 10)

        analysis = self.TestAnalysis()
        analysis.set_options(data_processor=DataProcessor("counts", [Probability("1")]))

        # data to analyze
        test_data0 = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=xvalues,
            param_dict={"amp": 1.0},
            op1=1,
            op2=True,
        )

        test_data1 = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=xvalues,
            param_dict={"amp": 0.5},
            op1=2,
            op2=True,
        )

        # get subset
        curve_data_of_1 = analysis._run_data_processing(
            raw_data=test_data0.data() + test_data1.data(),
            series=analysis.__series__,
        ).get_subset_of("curve1")

        # check x values
        ref_x = xvalues
        np.testing.assert_array_almost_equal(curve_data_of_1.x, ref_x)

        # check y values
        ref_y = fit_function.exponential_decay(xvalues, amp=1.0)
        np.testing.assert_array_almost_equal(curve_data_of_1.y, ref_y, decimal=3)

        # check data allocation
        ref_alloc = np.zeros(10, dtype=int)
        self.assertListEqual(list(curve_data_of_1.data_allocation), list(ref_alloc))

    def test_create_results(self):
        """Test creating analysis results."""
        analysis = self.TestAnalysis()
        analysis.set_options(
            result_parameters=["par0", ParameterRepr("par1", "Param1", "SomeUnit")],
        )

        pcov = np.diag(np.ones(5))
        popt = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0])
        fit_params = correlated_values(popt, pcov)

        fit_data = FitData(
            popt=fit_params,
            popt_keys=["par0", "par1", "par2", "par3", "par4", "par5"],
            pcov=pcov,
            reduced_chisq=2.0,
            dof=0,
            x_data=np.arange(5),
            y_data=np.arange(5),
        )

        outcomes = analysis._create_analysis_results(fit_data, quality="good", test_val=1)

        # entry name
        self.assertEqual(outcomes[0].name, "@Parameters_TestAnalysis")
        self.assertEqual(outcomes[1].name, "par0")
        self.assertEqual(outcomes[2].name, "Param1")

        # entry value
        self.assertEqual(outcomes[1].value, fit_params[0])
        self.assertEqual(outcomes[2].value, fit_params[1])

        # other metadata
        self.assertEqual(outcomes[2].quality, "good")
        self.assertEqual(outcomes[2].chisq, 2.0)
        ref_meta = {
            "test_val": 1,
            "unit": "SomeUnit",
        }
        self.assertDictEqual(outcomes[2].extra, ref_meta)

    def test_invalid_options(self):
        """Test setting invalid options."""
        analysis = self.TestAnalysis()

        class InvalidClass:
            """Dummy class."""

            pass

        with self.assertRaises(TypeError):
            analysis.set_options(data_processor=InvalidClass())

        with self.assertRaises(TypeError):
            analysis.set_options(curve_drawer=InvalidClass())


class TestCurveAnalysisIntegration(QiskitExperimentsTestCase):
    """Integration test for curve fit analysis through entire analysis.run function."""

    def setUp(self):
        super().setUp()
        self.xvalues = np.linspace(0.1, 1, 50)
        self.err_decimal = 2

    def test_run_single_curve_analysis(self):
        """Test analysis for single curve."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.exponential_decay(
                        x, amp=par0, lamb=par1, x0=par2, baseline=par3
                    ),
                    model_description=r"p_0 \exp(p_1 x + p_2) + p_3",
                )
            ],
        )
        ref_p0 = 0.9
        ref_p1 = 2.5
        ref_p2 = 0.0
        ref_p3 = 0.1

        test_data = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "lamb": ref_p1, "x0": ref_p2, "baseline": ref_p3},
        )
        analysis.set_options(
            p0={"par0": ref_p0, "par1": ref_p1, "par2": ref_p2, "par3": ref_p3},
            result_parameters=[ParameterRepr("par1", "parameter_name", "unit")],
        )

        results, _ = analysis._run_analysis(test_data)
        result = results[0]

        ref_popt = np.asarray([ref_p0, ref_p1, ref_p2, ref_p3])

        # check result data
        np.testing.assert_array_almost_equal(result.value, ref_popt, decimal=self.err_decimal)
        self.assertEqual(result.extra["dof"], 46)
        self.assertListEqual(result.extra["popt_keys"], ["par0", "par1", "par2", "par3"])
        self.assertDictEqual(result.extra["fit_models"], {"curve1": r"p_0 \exp(p_1 x + p_2) + p_3"})

        # special entry formatted for database
        result = results[1]
        self.assertEqual(result.name, "parameter_name")
        self.assertEqual(result.extra["unit"], "unit")
        self.assertAlmostEqual(result.value.nominal_value, ref_p1, places=self.err_decimal)

    def test_run_single_curve_fail(self):
        """Test analysis returns status when it fails."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.exponential_decay(
                        x, amp=par0, lamb=par1, x0=par2, baseline=par3
                    ),
                )
            ],
        )
        ref_p0 = 0.9
        ref_p1 = 2.5
        ref_p2 = 0.0
        ref_p3 = 0.1

        test_data = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "lamb": ref_p1, "x0": ref_p2, "baseline": ref_p3},
        )
        analysis.set_options(
            p0={"par0": ref_p0, "par1": ref_p1, "par2": ref_p2, "par3": ref_p3},
            bounds={"par0": [-10, 0], "par1": [-10, 0], "par2": [-10, 0], "par3": [-10, 0]},
            return_data_points=True,
        )

        # Try to fit with infeasible parameter boundary. This should fail.
        results, _ = analysis._run_analysis(test_data)

        # This returns only data point entry
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "@Data_TestAnalysis")

    def test_run_two_curves_with_same_fitfunc(self):
        """Test analysis for two curves. Curves shares fit model."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, par2, par3, par4: fit_function.exponential_decay(
                        x, amp=par0, lamb=par1, x0=par3, baseline=par4
                    ),
                    filter_kwargs={"exp": 0},
                ),
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, par2, par3, par4: fit_function.exponential_decay(
                        x, amp=par0, lamb=par2, x0=par3, baseline=par4
                    ),
                    filter_kwargs={"exp": 1},
                ),
            ],
        )
        ref_p0 = 0.9
        ref_p1 = 7.0
        ref_p2 = 5.0
        ref_p3 = 0.0
        ref_p4 = 0.1

        test_data0 = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "lamb": ref_p1, "x0": ref_p3, "baseline": ref_p4},
            exp=0,
        )

        test_data1 = simulate_output_data(
            func=fit_function.exponential_decay,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "lamb": ref_p2, "x0": ref_p3, "baseline": ref_p4},
            exp=1,
        )

        # merge two experiment data
        for datum in test_data1.data():
            test_data0.add_data(datum)

        analysis.set_options(
            p0={"par0": ref_p0, "par1": ref_p1, "par2": ref_p2, "par3": ref_p3, "par4": ref_p4}
        )
        results, _ = analysis._run_analysis(test_data0)
        result = results[0]

        ref_popt = np.asarray([ref_p0, ref_p1, ref_p2, ref_p3, ref_p4])

        # check result data
        np.testing.assert_array_almost_equal(result.value, ref_popt, decimal=self.err_decimal)

    def test_run_two_curves_with_two_fitfuncs(self):
        """Test analysis for two curves. Curves shares fit parameters."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.cos(
                        x, amp=par0, freq=par1, phase=par2, baseline=par3
                    ),
                    filter_kwargs={"exp": 0},
                ),
                SeriesDef(
                    name="curve2",
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.sin(
                        x, amp=par0, freq=par1, phase=par2, baseline=par3
                    ),
                    filter_kwargs={"exp": 1},
                ),
            ],
        )
        ref_p0 = 0.1
        ref_p1 = 2
        ref_p2 = -0.3
        ref_p3 = 0.5

        test_data0 = simulate_output_data(
            func=fit_function.cos,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "freq": ref_p1, "phase": ref_p2, "baseline": ref_p3},
            exp=0,
        )

        test_data1 = simulate_output_data(
            func=fit_function.sin,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "freq": ref_p1, "phase": ref_p2, "baseline": ref_p3},
            exp=1,
        )

        # merge two experiment data
        for datum in test_data1.data():
            test_data0.add_data(datum)

        analysis.set_options(p0={"par0": ref_p0, "par1": ref_p1, "par2": ref_p2, "par3": ref_p3})
        results, _ = analysis._run_analysis(test_data0)
        result = results[0]

        ref_popt = np.asarray([ref_p0, ref_p1, ref_p2, ref_p3])

        # check result data
        np.testing.assert_array_almost_equal(result.value, ref_popt, decimal=self.err_decimal)

    def test_run_fixed_parameters(self):
        """Test analysis when some of parameters are fixed."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, fixed_par2, par3: fit_function.cos(
                        x, amp=par0, freq=par1, phase=fixed_par2, baseline=par3
                    ),
                ),
            ],
            fixed_params=["fixed_par2"],
        )

        ref_p0 = 0.1
        ref_p1 = 2
        ref_p2 = -0.3
        ref_p3 = 0.5

        test_data = simulate_output_data(
            func=fit_function.cos,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "freq": ref_p1, "phase": ref_p2, "baseline": ref_p3},
        )

        analysis.set_options(
            p0={"par0": ref_p0, "par1": ref_p1, "par3": ref_p3},
            fixed_parameters={"fixed_par2": ref_p2},
        )

        results, _ = analysis._run_analysis(test_data)
        result = results[0]

        ref_popt = np.asarray([ref_p0, ref_p1, ref_p3])

        # check result data
        np.testing.assert_array_almost_equal(result.value, ref_popt, decimal=self.err_decimal)

    def test_fixed_param_is_missing(self):
        """Test raising an analysis error when fixed parameter is missing."""
        analysis = create_new_analysis(
            series=[
                SeriesDef(
                    name="curve1",
                    fit_func=lambda x, par0, par1, fixed_par2, par3: fit_function.cos(
                        x, amp=par0, freq=par1, phase=fixed_par2, baseline=par3
                    ),
                ),
            ],
            fixed_params=["fixed_p2"],
        )

        ref_p0 = 0.1
        ref_p1 = 2
        ref_p2 = -0.3
        ref_p3 = 0.5

        test_data = simulate_output_data(
            func=fit_function.cos,
            xvals=self.xvalues,
            param_dict={"amp": ref_p0, "freq": ref_p1, "phase": ref_p2, "baseline": ref_p3},
        )
        # do not define fixed_p2 here
        analysis.set_options(p0={"par0": ref_p0, "par1": ref_p1, "par3": ref_p3})
        with self.assertRaises(AnalysisError):
            analysis._run_analysis(test_data)


class TestFitOptions(QiskitExperimentsTestCase):
    """Unittest for fit option object."""

    def test_empty(self):
        """Test if default value is automatically filled."""
        opt = FitOptions(["par0", "par1", "par2"])

        # bounds should be default to inf tuple. otherwise crashes the scipy fitter.
        ref_opts = {
            "p0": {"par0": None, "par1": None, "par2": None},
            "bounds": {
                "par0": (-np.inf, np.inf),
                "par1": (-np.inf, np.inf),
                "par2": (-np.inf, np.inf),
            },
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_create_option_with_dict(self):
        """Create option and fill with dictionary."""
        opt = FitOptions(
            ["par0", "par1", "par2"],
            default_p0={"par0": 0, "par1": 1, "par2": 2},
            default_bounds={"par0": (0, 1), "par1": (1, 2), "par2": (2, 3)},
        )

        ref_opts = {
            "p0": {"par0": 0.0, "par1": 1.0, "par2": 2.0},
            "bounds": {"par0": (0.0, 1.0), "par1": (1.0, 2.0), "par2": (2.0, 3.0)},
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_create_option_with_array(self):
        """Create option and fill with array."""
        opt = FitOptions(
            ["par0", "par1", "par2"],
            default_p0=[0, 1, 2],
            default_bounds=[(0, 1), (1, 2), (2, 3)],
        )

        ref_opts = {
            "p0": {"par0": 0.0, "par1": 1.0, "par2": 2.0},
            "bounds": {"par0": (0.0, 1.0), "par1": (1.0, 2.0), "par2": (2.0, 3.0)},
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_override_partial_dict(self):
        """Create option and override value with partial dictionary."""
        opt = FitOptions(["par0", "par1", "par2"])
        opt.p0.set_if_empty(par1=3)

        ref_opts = {
            "p0": {"par0": None, "par1": 3.0, "par2": None},
            "bounds": {
                "par0": (-np.inf, np.inf),
                "par1": (-np.inf, np.inf),
                "par2": (-np.inf, np.inf),
            },
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_cannot_override_assigned_value(self):
        """Test cannot override already assigned value."""
        opt = FitOptions(["par0", "par1", "par2"])
        opt.p0.set_if_empty(par1=3)
        opt.p0.set_if_empty(par1=5)

        ref_opts = {
            "p0": {"par0": None, "par1": 3.0, "par2": None},
            "bounds": {
                "par0": (-np.inf, np.inf),
                "par1": (-np.inf, np.inf),
                "par2": (-np.inf, np.inf),
            },
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_can_override_assigned_value_with_dict_access(self):
        """Test override already assigned value with direct dict access."""
        opt = FitOptions(["par0", "par1", "par2"])
        opt.p0["par1"] = 3
        opt.p0["par1"] = 5

        ref_opts = {
            "p0": {"par0": None, "par1": 5.0, "par2": None},
            "bounds": {
                "par0": (-np.inf, np.inf),
                "par1": (-np.inf, np.inf),
                "par2": (-np.inf, np.inf),
            },
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_cannot_override_user_option(self):
        """Test cannot override already assigned value."""
        opt = FitOptions(["par0", "par1", "par2"], default_p0={"par1": 3})
        opt.p0.set_if_empty(par1=5)

        ref_opts = {
            "p0": {"par0": None, "par1": 3, "par2": None},
            "bounds": {
                "par0": (-np.inf, np.inf),
                "par1": (-np.inf, np.inf),
                "par2": (-np.inf, np.inf),
            },
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_set_operation(self):
        """Test if set works and duplicated entry is removed."""
        opt1 = FitOptions(["par0", "par1"], default_p0=[0, 1])
        opt2 = FitOptions(["par0", "par1"], default_p0=[0, 1])
        opt3 = FitOptions(["par0", "par1"], default_p0=[0, 2])

        opts = set()
        opts.add(opt1)
        opts.add(opt2)
        opts.add(opt3)

        self.assertEqual(len(opts), 2)

    def test_detect_invalid_p0(self):
        """Test if invalid p0 raises Error."""
        with self.assertRaises(AnalysisError):
            # less element
            FitOptions(["par0", "par1", "par2"], default_p0=[0, 1])

    def test_detect_invalid_bounds(self):
        """Test if invalid bounds raises Error."""
        with self.assertRaises(AnalysisError):
            # less element
            FitOptions(["par0", "par1", "par2"], default_bounds=[(0, 1), (1, 2)])

        with self.assertRaises(AnalysisError):
            # not min-max tuple
            FitOptions(["par0", "par1", "par2"], default_bounds=[0, 1, 2])

        with self.assertRaises(AnalysisError):
            # max-min tuple
            FitOptions(["par0", "par1", "par2"], default_bounds=[(1, 0), (2, 1), (3, 2)])

    def test_detect_invalid_key(self):
        """Test if invalid key raises Error."""
        opt = FitOptions(["par0", "par1", "par2"])

        with self.assertRaises(AnalysisError):
            opt.p0.set_if_empty(par3=3)

    def test_set_extra_options(self):
        """Add extra fitter options."""
        opt = FitOptions(
            ["par0", "par1", "par2"], default_p0=[0, 1, 2], default_bounds=[(0, 1), (1, 2), (2, 3)]
        )
        opt.add_extra_options(ex1=0, ex2=1)

        ref_opts = {
            "p0": {"par0": 0.0, "par1": 1.0, "par2": 2.0},
            "bounds": {"par0": (0.0, 1.0), "par1": (1.0, 2.0), "par2": (2.0, 3.0)},
            "ex1": 0,
            "ex2": 1,
        }

        self.assertDictEqual(opt.options, ref_opts)

    def test_complicated(self):
        """Test for realistic operations for algorithmic guess with user options."""
        user_p0 = {"par0": 1, "par1": None}
        user_bounds = {"par0": None, "par1": (-100, 100)}

        opt = FitOptions(
            ["par0", "par1", "par2"],
            default_p0=user_p0,
            default_bounds=user_bounds,
        )

        # similar computation in algorithmic guess

        opt.p0.set_if_empty(par0=5)  # this is ignored because user already provided initial guess
        opt.p0.set_if_empty(par1=opt.p0["par0"] * 2 + 3)  # user provided guess propagates

        opt.bounds.set_if_empty(par0=(0, 10))  # this will be set
        opt.add_extra_options(fitter="algo1")

        opt1 = opt.copy()  # copy options while keeping previous values
        opt1.p0.set_if_empty(par2=opt1.p0["par0"] + opt1.p0["par1"])

        opt2 = opt.copy()
        opt2.p0.set_if_empty(par2=opt2.p0["par0"] * 2)  # add another p2 value

        ref_opt1 = {
            "p0": {"par0": 1.0, "par1": 5.0, "par2": 6.0},
            "bounds": {"par0": (0.0, 10.0), "par1": (-100.0, 100.0), "par2": (-np.inf, np.inf)},
            "fitter": "algo1",
        }

        ref_opt2 = {
            "p0": {"par0": 1.0, "par1": 5.0, "par2": 2.0},
            "bounds": {"par0": (0.0, 10.0), "par1": (-100.0, 100.0), "par2": (-np.inf, np.inf)},
            "fitter": "algo1",
        }

        self.assertDictEqual(opt1.options, ref_opt1)
        self.assertDictEqual(opt2.options, ref_opt2)


class TestBackwardCompatibility(QiskitExperimentsTestCase):
    """Test case for backward compatibility."""

    def test_old_fixed_param_attributes(self):
        """Test if old class structure for fixed param is still supported."""

        class _DeprecatedAnalysis(CurveAnalysis):
            __series__ = [
                SeriesDef(
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.exponential_decay(
                        x, amp=par0, lamb=par1, x0=par2, baseline=par3
                    ),
                )
            ]

            __fixed_parameters__ = ["par1"]

            @classmethod
            def _default_options(cls):
                opts = super()._default_options()
                opts.par1 = 2

                return opts

        with self.assertWarns(DeprecationWarning):
            instance = _DeprecatedAnalysis()

        self.assertDictEqual(instance.options.fixed_parameters, {"par1": 2})

    def test_loading_data_with_deprecated_fixed_param(self):
        """Test loading old data with fixed parameters as standalone options."""

        class _DeprecatedAnalysis(CurveAnalysis):
            __series__ = [
                SeriesDef(
                    fit_func=lambda x, par0, par1, par2, par3: fit_function.exponential_decay(
                        x, amp=par0, lamb=par1, x0=par2, baseline=par3
                    ),
                )
            ]

        with self.assertWarns(DeprecationWarning):
            # old option data structure, i.e. fixed param as a standalone option
            # the analysis instance fixed parameters might be set via the experiment instance
            instance = _DeprecatedAnalysis.from_config({"options": {"par1": 2}})

        self.assertDictEqual(instance.options.fixed_parameters, {"par1": 2})