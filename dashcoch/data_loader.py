from configparser import ConfigParser
from datetime import date, datetime
import pandas as pd
from pytz import timezone


class DataLoader:
    def __init__(self, parser: ConfigParser):
        # Load info on the latest updates
        self.last_updated = pd.read_csv(
            parser.get("urls", "last_updated"), index_col=[0]
        ).sort_values(by=["Date", "Time"], ascending=False)

        self.last_updated = self.__get_iso(self.last_updated)

        # Load the actual data
        self.swiss_cases = pd.read_csv(parser.get("urls", "swiss_cases"))
        self.swiss_fatalities = pd.read_csv(parser.get("urls", "swiss_fatalities"))
        self.swiss_hospitalizations = pd.read_csv(
            parser.get("urls", "swiss_hospitalizations")
        )
        self.swiss_icu = pd.read_csv(parser.get("urls", "swiss_icu"))
        self.swiss_vent = pd.read_csv(parser.get("urls", "swiss_vent"))
        self.swiss_releases = pd.read_csv(parser.get("urls", "swiss_releases"))

        self.swiss_demography = pd.read_csv(
            parser.get("urls", "swiss_demography"), index_col=0
        )
        self.world_cases = self.__simplify_world_data(
            pd.read_csv(parser.get("urls", "world_cases"))
        )
        self.world_fataltities = self.__simplify_world_data(
            pd.read_csv(parser.get("urls", "world_fatalities"))
        )

        self.world_population = self.__get_world_population()

        self.swiss_cases_by_date = self.swiss_cases.set_index("Date")
        self.swiss_fatalities_by_date = self.swiss_fatalities.set_index("Date")
        self.swiss_hospitalizations_by_date = self.swiss_hospitalizations.set_index(
            "Date"
        )

        self.swiss_cases_by_date_filled = self.swiss_cases_by_date.fillna(
            method="ffill", axis=0
        )

        self.swiss_cases_by_date_diff = self.swiss_cases_by_date_filled.diff().replace(
            0, float("nan")
        )
        self.swiss_fatalities_by_date_diff = self.swiss_fatalities_by_date.diff().replace(
            0, float("nan")
        )

        self.swiss_hospitalizations_by_date_diff = self.swiss_hospitalizations_by_date.diff().replace(
            0, float("nan")
        )

        self.swiss_cases_by_date_filled = self.swiss_cases_by_date.fillna(
            method="ffill", axis=0
        )

        self.swiss_fatalities_by_date_filled = self.swiss_fatalities_by_date.fillna(
            method="ffill", axis=0
        )

        self.swiss_hospitalizations_by_date_filled = self.swiss_hospitalizations_by_date.fillna(
            method="ffill", axis=0
        )

        self.swiss_case_fatality_rates = (
            self.swiss_fatalities_by_date_filled / self.swiss_cases_by_date_filled
        )

        self.swiss_cases_by_date_filled_per_capita = (
            self.__get_swiss_cases_by_date_filled_per_capita()
        )

        self.latest_date = self.__get_latest_date()
        self.updated_cantons = self.__get_updated_cantons()
        self.new_swiss_cases = self.__get_new_cases()
        self.total_swiss_cases = self.__get_total_swiss_cases()
        self.total_swiss_fatalities = self.__get_total_swiss_fatalities()
        self.swiss_case_fatality_rate = (
            self.total_swiss_fatalities / self.total_swiss_cases
        )

        # Put the date at the end
        self.swiss_cases_as_dict = self.swiss_cases.to_dict("list")
        date_tmp = self.swiss_cases_as_dict.pop("Date")
        self.swiss_cases_as_dict["Date"] = date_tmp
        self.swiss_cases_normalized_as_dict = (
            self.__get_swiss_cases_as_normalized_dict()
        )

        self.swiss_fatalities_as_dict = self.swiss_fatalities.to_dict("list")
        self.canton_labels = [
            canton
            for canton in self.swiss_cases_as_dict
            if canton != "CH" and canton != "Date"
        ]
        self.cantonal_centres = self.__get_cantonal_centres()

        #
        # World related data
        #

        self.world_case_fatality_rate = (
            self.world_fataltities.iloc[-1] / self.world_cases.iloc[-1]
        )

        self.swiss_world_cases_normalized = self.__get_swiss_world_cases_normalized()

    def __get_iso(self, df):
        isos = []
        updated_today = []
        for i, row in df.iterrows():
            t = row["Time"]
            if len(t) == 4:
                t = "0" + t
            iso = datetime.fromisoformat(row["Date"] + "T" + t + ":00")
            isos.append(iso)
            updated_today.append(iso.date() == datetime.today().date())

        df["ISO"] = isos
        df["Updated_Today"] = updated_today

        return df

    def __get_latest_date(self):
        return self.swiss_cases.iloc[len(self.swiss_cases) - 1]["Date"]

    def __get_updated_cantons(self):
        l = len(self.swiss_cases_by_date)
        return [
            canton
            for canton in self.swiss_cases_by_date.iloc[l - 1][
                self.swiss_cases_by_date.iloc[l - 1].notnull()
            ].index
        ]

    def __get_swiss_cases_by_date_filled_per_capita(self):
        tmp = self.swiss_cases_by_date_filled.copy()

        for column in tmp:
            tmp[column] = (
                tmp[column] / self.swiss_demography["Population"][column] * 10000
            )
        return tmp

    def __get_new_cases(self):
        if (
            date.fromisoformat(self.latest_date)
            != datetime.now(timezone("Europe/Zurich")).date()
        ):
            return 0

        l = len(self.swiss_cases_by_date_filled)
        return (
            self.swiss_cases_by_date_filled.diff().iloc[l - 1].sum()
            - self.swiss_cases_by_date_filled.diff().iloc[l - 1]["CH"]
        )

    def __get_total_swiss_cases(self):
        l = len(self.swiss_cases_by_date_filled)
        return (
            self.swiss_cases_by_date_filled.iloc[l - 1].sum()
            - self.swiss_cases_by_date_filled.iloc[l - 1]["CH"]
        )

    def __get_total_swiss_fatalities(self):
        return self.swiss_fatalities_by_date_filled.iloc[-1]["CH"]

    def __get_swiss_cases_as_normalized_dict(self):
        tmp = [
            (
                str(canton),
                [
                    round(i, 2)
                    for i in self.swiss_cases_as_dict[canton]
                    / self.swiss_demography["Population"][canton]
                    * 10000
                ],
            )
            for canton in self.swiss_cases_as_dict
            if canton != "Date"
        ]
        tmp.append(("Date", self.swiss_cases_as_dict["Date"]))
        return dict(tmp)

    def __simplify_world_data(self, df: pd.DataFrame):
        df.drop(columns=["Lat", "Long"], inplace=True)
        df["Province/State"].fillna("", inplace=True)
        df = df.rename(columns={"Country/Region": "Day"})
        df = df.groupby("Day").sum()
        df = df.T
        df.drop(
            df.columns.difference(
                [
                    "France",
                    "Germany",
                    "Italy",
                    "Korea, South",
                    "Spain",
                    "United Kingdom",
                    "US",
                ]
            ),
            1,
            inplace=True,
        )
        df.index = range(0, len(df))
        return df

    def __get_swiss_world_cases_normalized(self, min_prevalence: int = 0.4):
        tmp = self.world_cases.copy()
        tmp["Switzerland"] = pd.Series(self.swiss_cases_as_dict["CH"])

        for column in tmp:
            tmp[column] = tmp[column] / self.world_population[column] * 10000

        tmp[tmp < min_prevalence] = 0
        for column in tmp:
            while tmp[column].iloc[0] == 0:
                tmp[column] = tmp[column].shift(-1)
        tmp.dropna(how="all", inplace=True)

        return tmp

    def __get_world_population(self):
        return {
            "France": 65273511,
            "Germany": 83783942,
            "Italy": 60461826,
            "Spain": 46754778,
            "US": 331002651,
            "United Kingdom": 67886011,
            "Switzerland": 8654622,
            "Korea, South": 51269185,
        }

    def __get_cantonal_centres(self):
        return {
            "AG": {"lat": 47.40966, "lon": 8.15688},
            "AR": {"lat": 47.366352 + 0.05, "lon": 9.36791},
            "AI": {"lat": 47.317264, "lon": 9.416754},
            "BL": {"lat": 47.45176, "lon": 7.702414},
            "BS": {"lat": 47.564869, "lon": 7.615259},
            "BE": {"lat": 46.823608, "lon": 7.636667},
            "FR": {"lat": 46.718391, "lon": 7.074008},
            "GE": {"lat": 46.220528, "lon": 6.132935},
            "GL": {"lat": 46.981042 - 0.05, "lon": 9.065751},
            "GR": {"lat": 46.656248, "lon": 9.628198},
            "JU": {"lat": 47.350744, "lon": 7.156107},
            "LU": {"lat": 47.067763, "lon": 8.1102},
            "NE": {"lat": 46.995534, "lon": 6.780126},
            "NW": {"lat": 46.926755, "lon": 8.405302},
            "OW": {"lat": 46.854527 - 0.05, "lon": 8.244317 - 0.1},
            "SH": {"lat": 47.71357, "lon": 8.59167},
            "SZ": {"lat": 47.061787, "lon": 8.756585},
            "SO": {"lat": 47.304135, "lon": 7.639388},
            "SG": {"lat": 47.2332 - 0.05, "lon": 9.274744},
            "TI": {"lat": 46.295617, "lon": 8.808924},
            "TG": {"lat": 47.568715, "lon": 9.091957},
            "UR": {"lat": 46.771849, "lon": 8.628586},
            "VD": {"lat": 46.570091, "lon": 6.657809 - 0.1},
            "VS": {"lat": 46.209567, "lon": 7.604659},
            "ZG": {"lat": 47.157296, "lon": 8.537294},
            "ZH": {"lat": 47.41275, "lon": 8.65508},
        }
