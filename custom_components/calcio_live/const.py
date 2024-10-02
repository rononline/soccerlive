import logging
_LOGGER = logging.getLogger(__name__)

DOMAIN = "calcio_live"
CONF_COMPETITION_CODE = "competition_code"

COMPETITIONS = {
    'ita.1': 'Serie A',
    'ger.1': 'Bundesliga',
    'esp.1': 'La Liga',
    'por.1': 'Primeira Liga',
    'uefa.europa_qual': 'UEFA Europa League Qualifying',
    'uefa.champions_qual': 'UEFA Champions League Qualifying',
    'fifa.intercontinental.cup': 'FIFA Intercontinental Cup',
    'mex.2': 'Liga de Expansión MX',
    'arg.5': 'Primera C Metropolitana',
    'wal.1': 'Cymru Premier',
    'ven.2': 'Segunda División Venezolana',
    'arg.4': 'Primera D Metropolitana',
    'irl.1': 'League of Ireland Premier Division',
    'uru.2': 'Segunda División Uruguaya',
    'aut.promotion.relegation': 'Austrian Promotion/Relegation Playoff',
    'arg.3': 'Primera B Metropolitana',
    'den.promotion.relegation': 'Danish Promotion/Relegation Playoff',
    'chi.2': 'Primera B de Chile',
    'ned.1': 'Eredivisie',
    'nor.1': 'Eliteserien',
    'swe.1': 'Allsvenskan',
    'sui.1': 'Swiss Super League',
    'tur.1': 'Super Lig',
    'usa.1': 'Major League Soccer (MLS)',
    'arg.copa': 'Copa Argentina',
}
