import copy
import importlib
from enum import Enum
from typing import Dict, List, Optional, Union

from autoval.lib.utils.autoval_exceptions import AutovalFileNotFound
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.file_actions import FileActions
from autoval.lib.utils.generic_utils import GenericUtils
from autoval.lib.utils.site_utils import SiteUtils as path
from autoval.plugins.plugin_manager import PluginManager


class PluginType(Enum):
    IMPORTPATH = "havoc.autoval.lib.utils.fb.data_plugin."
    FILESYSTEM = f"{IMPORTPATH}file_plugin"
    XDB = f"{IMPORTPATH}xdb_plugin"
    HI5 = f"{IMPORTPATH}hi5_actions"


class UperfTestUtil:
    """
    Base class for uperf tests.
    Hosts the APIs to access the relevant test data for the user provided configuration inputs.
    It also masks the undelying data store
    Towards the end it also collects certain config data that will enable better filtering of
    performance data and store them in config_results.json
    """

    def get_performance_data(
        self,
        # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
        #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting
        #  errors.
        config_dict: Dict,
        number_of_recs: int = 10,
        db_type: Optional[str] = None,
        # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
        #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    ) -> List[Dict]:
        """
        Get the right plugin for the user environment and queries the
        data for the user provided configuration input

        query: input dictionary with one or more key/value pairs. This input will be used
               as a condition to query the relevant data from the datastore with the use of
               the plugin identified for the environment
               eg: {"hostname": "rtptest8445.prn6.facebook.com", "BIOS_Revision": 5.19}
        db_type: type of database to be used.
            eg: xdb for havoc
        Returns:
            object: retrives the historical run results
        """
        try:
            return self.get_data_plugin(db_type).read_data(config_dict, number_of_recs)
        except Exception as e:
            AutovalLog.log_info(f"Unable to perform read with following error {e}")
            return []

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_config_for_perf_compare(self, host):
        return self.get_data_plugin().get_config_for_perf_compare(host)

    def write(self) -> None:
        """
        Performs write operations, writes the active_run dict to file, database based on the
        active plugin
        """
        try:
            self.get_data_plugin().write_data()
            AutovalLog.log_info("Writing collected metrics")
        except Exception as e:
            AutovalLog.log_info(f"Unable to perform write with following error  {e}")

    # pyre-fixme[3]: Return type must be annotated.
    def get_data_plugin(self, db_type: Optional[str] = None):
        """
        provides active plugin to which the data needs to be written,
        Primary will be the file plugin and active will be the DB plugin.

        Returns:
            object: relevent plugin import, DB/File based
        """
        data_plugin_primary = None
        if not db_type:
            try:
                data_plugin_primary = path.get_data_plugins().upper()
            except Exception as e:

                AutovalLog.log_info(
                    f"Unable to get plugin info with following error {e}"
                )
        else:
            data_plugin_primary = db_type.upper()
        if data_plugin_primary:
            plugin = PluginType[data_plugin_primary].value
            plugin_module = importlib.import_module(plugin, ".")
            return plugin_module

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def update_config_dict(self, config_dict, conf_file: str):
        try:
            current_config_data = FileActions.read_data(conf_file, json_file=True)
        except AutovalFileNotFound:
            current_config_data = {}
        for comp, comp_dict in config_dict.items():
            for _id, config_data in comp_dict.items():
                current_config_data[comp][_id].update(config_data)
        return current_config_data


class ThresholdException(Exception):
    pass


class FormulaException(Exception):
    pass


class Threshold:
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, threshold):
        if threshold:
            for k, v in threshold.items():
                setattr(self, k, v)

    # pyre-fixme[3]: Return type must be annotated.
    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v


class ThresholdConfig:
    # pyre-fixme[3]: Return type must be annotated.
    def __init__(self):
        # pyre-fixme[4]: Attribute must be annotated.
        self.formula_map = {
            "multiply_with_cpu_speed": self.multiply_with_cpu_speed,
            "multiply_with_cpu_threads": self.multiply_with_cpu_threads,
            "multiply_with_theoretical_total_bw": self.multiply_with_theoretical_total_bw,
        }

    # pyre-fixme[3]: Return type must be annotated.
    def get_threshold(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        filepath,
        # pyre-fixme[2]: Parameter must be annotated.
        user_criteria,
        # pyre-fixme[2]: Parameter must be annotated.
        user_metric_list,
        # pyre-fixme[2]: Parameter must be annotated.
        return_partial_matches=False,
        # pyre-fixme[2]: Parameter must be annotated.
        must_match_criteria=None,
        # pyre-fixme[2]: Parameter must be annotated.
        formula_args=None,
    ):
        """
        This is the API exposed to the user to read a threshold from a config file stored in the configerator

        The API takes the list of metrics, file path and the criterias that have to match and returns an Threshold object in Dict indexed by the metric string.

        The API returns if there is an exact match (matches all the user criterias)

        Else the user can get the partially matched thresholds as well by providing must_match_criterias

        some thresholds can be stored as formulas. So the API takes the args the formula requires to compute the the threshold value
        """
        if not filepath:
            return {}

        data = PluginManager.get_plugin_cls("config_datasource")().read_config_as_json(
            filepath
        )

        if not data:
            return {}

        rules = data["rules"]
        thresholds = {}
        selected_rules = []

        if "project_name" in user_criteria:
            user_criteria["model_ids"] = self.convert_project_name_to_model_ids(
                [user_criteria["project_name"]]
            )
            # remove 'project_name'  from both the criterias (user and rule) as it is been converted to model_ids
            del user_criteria["project_name"]

        if must_match_criteria:
            must_match_criteria = [
                x.replace("project_name", "model_ids") for x in must_match_criteria
            ]

        for metric in user_metric_list:
            # Collect the rules that has this metric defined
            selected_rules = self.choose_relevant_rules_for_metric(rules, metric)

            thresholds[metric] = self.get_a_match_for_metric(
                metric,
                selected_rules,
                user_criteria,
                formula_args,
                must_match_criteria,
                return_partial_matches,
            )
            if hasattr(thresholds[metric], "formula"):

                thresholds[metric] = self._apply_formula(
                    thresholds[metric], formula_args
                )

        return thresholds

    # pyre-fixme[3]: Return type must be annotated.
    def choose_relevant_rules_for_metric(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        rules,
        # pyre-fixme[2]: Parameter must be annotated.
        metric,
    ):
        selected_rules = []
        for rule in rules:
            metric_threshold_pairs = rule["metric_threshold_pair"]
            for metric_threshold_pair in metric_threshold_pairs:
                if metric == metric_threshold_pair["metric"]:
                    selected_rules.append(rule)

        return selected_rules

    # pyre-fixme[3]: Return type must be annotated.
    def get_a_match_for_metric(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        metric,
        # pyre-fixme[2]: Parameter must be annotated.
        rules,
        # pyre-fixme[2]: Parameter must be annotated.
        user_criteria,
        # pyre-fixme[2]: Parameter must be annotated.
        formula_args,
        # pyre-fixme[2]: Parameter must be annotated.
        must_match_criteria,
        # pyre-fixme[2]: Parameter must be annotated.
        return_partial_matches,
    ):
        """
        Returns one threshold object for a given metric

        It can either be an exact match for the user criteria or one of the partial matches that was voted as best

        Voting is based on couple of factors
            1) must_match_criteria (if provided by the user)- the attributes that weigh high to select the threshold
            2)Else one of the partial matches will be chosen based on the number of matching attributes present in the match


        @params
        metric - Metric string
        rules: rules that have definition for the metric
        user_criteria: Criterias supplied  by the user
        formula_args: metrics can be stored as formulas. values needed for the formula
        must_match_criteria: User might want to see the thresholds that matches close to their criteria. Hence can provide a list of attrs that must match

        @return
        Threshold object
        """
        # metric_threshold = {}
        partially_matched_thresholds = []  # List of Threshold Type
        metric_threshold = Threshold({})
        common_threshold = (
            {}
        )  # Eg: Threshold for all the models, all number of memory channels etc
        default_threshold = (
            {}
        )  # Default threshold irrespective any criteria hence no criteria defined for this rule

        for rule in rules:
            matches = {}
            if "criteria" not in rule and rule["name"] == "default_rule":
                default_threshold = self.store_a_match_as_threshold(
                    metric, matches, rule, user_criteria, match_type="default"
                )
                continue

            if not set(user_criteria.keys()) & set(rule["criteria"].keys()):
                # This rule has not listed any of the  user criteria ; Continue with the next rule
                continue

            # Check for matching criterias in this rule
            rule_criteria = rule["criteria"]
            rule_type = []
            for k, v in user_criteria.items():
                is_match, _rule_type = self.is_match(k, v, rule_criteria)
                rule_type.append(_rule_type)
                if is_match:
                    matches.update({k: v})
            if matches and len(matches) == len(user_criteria):
                metric_threshold = self.store_a_match_as_threshold(
                    metric, matches, rule, user_criteria, match_type=rule_type
                )
                if all(match_type == "exact_match" for match_type in rule_type):
                    return metric_threshold
                else:
                    # This could be a threshold that is common for one of the criterias
                    # Eg: threshold for all the model ids/ all the memory channel
                    # This could be a match, if we dont have an exact match
                    # So lets save this and decide later
                    common_threshold = Threshold({})
                    common_threshold = copy.copy(metric_threshold)

            elif matches and return_partial_matches:
                if must_match_criteria:
                    if set(must_match_criteria).issubset(set(matches.keys())):
                        # This rule has a partial match for this metric, store it
                        partially_matched_thresholds.append(
                            self.store_a_match_as_threshold(
                                metric,
                                matches,
                                rule,
                                user_criteria,
                                match_type="partial_match",
                            )
                        )

                else:
                    partially_matched_thresholds.append(
                        self.store_a_match_as_threshold(
                            metric,
                            matches,
                            rule,
                            user_criteria,
                            match_type="partial_match",
                        )
                    )

        if partially_matched_thresholds:
            if len(partially_matched_thresholds) > 1:
                # pyre-fixme[20]: Argument `must_match_criteria` expected.
                metric_threshold = self.vote_a_threshold(partially_matched_thresholds)

                if metric_threshold:
                    return metric_threshold
            else:  # Only one threshold found. Return it
                return partially_matched_thresholds[0]

        elif common_threshold:
            return common_threshold

        elif default_threshold:
            return default_threshold
        else:
            raise ThresholdException(
                f"No thresholds matches with the user criteria for {metric}"
            )

    # pyre-fixme[3]: Return type must be annotated.
    def vote_a_threshold(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        partially_matched_thresholds,
        # pyre-fixme[2]: Parameter must be annotated.
        must_match_criteria,
    ):
        if must_match_criteria:
            for partial_match in partially_matched_thresholds:
                # pyre-fixme[16]: `Set` has no attribute `isubset`.
                if set(must_match_criteria).isubset(
                    partial_match.matched_criterias.keys()
                ):
                    # Vote this rule
                    voted_rule = partial_match

        elif len(partially_matched_thresholds) > 1:
            partially_matched_thresholds = sorted(
                partially_matched_thresholds, key=lambda x: len(x.matches), reverse=True
            )
            voted_rule = partially_matched_thresholds[0]

        # pyre-fixme[61]: `voted_rule` is undefined, or not always defined.
        return voted_rule

    # pyre-fixme[3]: Return type must be annotated.
    def store_a_match_as_threshold(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        metric,
        # pyre-fixme[2]: Parameter must be annotated.
        matches,
        # pyre-fixme[2]: Parameter must be annotated.
        rule,
        # pyre-fixme[2]: Parameter must be annotated.
        user_criteria,
        # pyre-fixme[2]: Parameter must be annotated.
        match_type,
    ):
        _metric_threshold = {}
        for metric_threshold in rule["metric_threshold_pair"]:
            if metric_threshold["metric"] == metric:
                _metric_threshold = copy.copy(metric_threshold)
                _metric_threshold["match_type"] = match_type
                _metric_threshold["matched_criterias"] = list(matches)
                if "name" in rule:
                    _metric_threshold["configerator_rule_name"] = rule["name"]
        return Threshold(_metric_threshold)

    def evaluate_formula_expression(
        self,
        formula: str,
        # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
        #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting
        #  errors.
        formula_args: Dict,
    ) -> Union[int, float]:
        return GenericUtils.evaluate_expression(formula, formula_args)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _apply_formula(self, threshold, formula_args):
        if not threshold.formula:
            print("This threshold does not have a formula")
            return threshold.value

        formula = threshold.formula
        if formula in self.formula_map:
            threshold.value = self.formula_map[formula](threshold.value, formula_args)
        else:
            threshold.value = self.evaluate_formula_expression(formula, formula_args)

        return threshold

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def is_match(self, key, value, rule_criteria):
        if key in rule_criteria:
            if rule_criteria[key] == value:
                return True, "exact_rule"

            if isinstance(rule_criteria[key], list) or isinstance(
                rule_criteria[key], set
            ):
                if set(value).issubset(set(rule_criteria[key])):
                    return True, "exact_match"
                elif len(rule_criteria[key]) == 0:
                    return True, "common_rule"
                    # for eg: if the model id exists or its empty list , which means it matches for all the model ids

            if str(rule_criteria[key]).isdigit():
                if rule_criteria[key] == 0:
                    return True, "common_rule"

        return False, None

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def convert_project_name_to_model_ids(self, project_name_list):
        model_ids = []
        project_serf_names = []
        model_class_serf_map = []
        model_class_serf_map = FileActions.read_resource_file(
            file_path="cfg/site_settings/models_all.json",
            module="havoc.autoval",
        )
        for project in project_name_list:
            for _model_map in model_class_serf_map:
                if project in _model_map["name"] or project in _model_map["class"]:
                    project_serf_names.append(_model_map["serf_model"])

        model_type_map_file_path = "havoc/autoval/model_id_type_map/model_id_type_map"
        data = PluginManager.get_plugin_cls("config_datasource")().read_config_as_json(
            model_type_map_file_path
        )
        model_map_dict = data["model_map"]
        for project_name in project_serf_names:
            if project_name in model_map_dict:
                model_ids.extend(model_map_dict[project_name])
                if not model_ids:
                    raise ThresholdException(
                        f"model_id_type_map.json does have the mapping for {project_name}"
                    )
        return model_ids

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def multiply_with_cpu_speed(self, value, formula_args):
        if "cpu_speed" in formula_args:
            return value * formula_args["cpu_speed"]
        raise FormulaException("Missing value for cpu_speed")

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def multiply_with_cpu_threads(self, value, formula_args):
        if "cpu_threads" in formula_args:
            return value * formula_args["cpu_threads"]
        raise FormulaException("Missing value for cpu_threads")

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def multiply_with_theoretical_total_bw(self, value, formula_args):
        if "theoretical_total_bw" in formula_args:
            return value * formula_args["theoretical_total_bw"]
        raise FormulaException("Missing value for theoretical_total_bw")
