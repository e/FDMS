import pandas as pd

from fdms.config.scale_correction import SCALES
from fdms.utils.series import COLUMN_ORDER, get_series_noindex, get_series
from fdms.utils.splicer import Splicer


class StepMixin:
    country = 'BE'
    frequency = 'Annual'
    scale = 'Units'

    def __init__(self, country=country, frequency=frequency, scale=scale, scales={}):
        self.country = country
        self.frequency = frequency
        self.scale = scale
        self.scales = scales
        self.scale_correction = {}
        self.result = pd.DataFrame(columns=COLUMN_ORDER)

    def update_result(self, series):
        series = self.result.loc[(self.result['Country Ameco'] == series['Country Ameco']) & (
            self.result['Variable Code'] == series['Variable Code'])]
        if series.empty:
            self.result.append(series, ignore_index=True, sort=True)
        else:
            self.result.iloc[series.index.values[0]] = series

    def get_scale(self, variable):
        expected = SCALES.get(variable)
        input_data = self.scales.get(variable)
        if expected:
            if input_data != expected:
                if variable not in self.scale_correction:
                    self.scale_correction[variable] = (input_data, expected)
                with open('errors_scale.txt', 'a') as f:
                    f.write(' '.join([variable, expected or '-', input_data or '-', '\n']))
        return (SCALES.get(variable) or self.scales.get(variable) or self.scale).capitalize()

    def apply_scale(self):
        codes = {'Units': 0, 'Thousands': 1, 'Millions': 2, 'Billions': 3, '-': 0}
        for variable in self.scale_correction:
            meta = pd.Series(self.get_meta(variable))
            series = get_series(self.result, self.country, variable)
            orig, expected = self.scale_correction[variable]
            if all([x is not None for x in [orig, expected]]):
                series = series * pow(1000, codes[orig] - codes[expected])
            try:
                self.result.loc[self.country, variable] = pd.concat([meta, series])
            except:
                with open('raro.txt', 'a') as f:
                    f.write(variable + '\n')

    def get_meta(self, variable):
        return {'Country Ameco': self.country, 'Variable Code': variable, 'Frequency': self.frequency,
                'Scale': self.get_scale(variable)}


class SumAndSpliceMixin:
    def _sum_and_splice(self, addends, df, ameco_h_df):
        splicer = Splicer()
        for variable, sources in addends.items():
            series_meta = self.get_meta(variable)
            try:
                base_series = get_series(ameco_h_df, self.country, variable)
            except KeyError:
                base_series = None
            splice_series = pd.Series()
            for source in sources:
                factor = 1
                if source.startswith('-'):
                    source = source[1:]
                    factor = -1
                try:
                    source_data = factor * get_series(df, self.country, source)
                except KeyError:
                    source_data = factor * get_series_noindex(self.result, self.country, source)
                splice_series = splice_series.add(source_data, fill_value=0)

            if base_series is None:
                series_data = splice_series
            else:
                series_data = splicer.butt_splice(base_series, splice_series, kind='forward')
            if self.country == 'JP' and variable in ['UUTG.1.0.0.0', 'URTG.1.0.0.0']:
                if variable == 'URTG.1.0.0.0':
                    new_sources = ['UUTG.1.0.0.0', 'UBLG.1.0.0.0']
                    splice_series = get_series_noindex(
                        self.result, self.country, new_sources[0]) + get_series_noindex(
                        self.result, self.country, new_sources[1]
                    )
                series_data = splicer.ratio_splice(base_series, splice_series, kind='forward')
            series = pd.Series(series_meta)
            series = series.append(series_data)
            self.result = self.result.append(series, ignore_index=True, sort=True)
