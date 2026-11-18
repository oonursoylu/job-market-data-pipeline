-- Aliases must already be in the form the matcher produces: lower case, letters, digits,
-- German umlauts and single spaces, separated by pipes. An alias such as "scikit-learn"
-- or "Power BI" would never match, because the posting text never contains it in that form.
select
    skill,
    pattern

from {{ ref('skill_dictionary') }}

where pattern !~ '^[a-z0-9äöüß]+( [a-z0-9äöüß]+)*(\|[a-z0-9äöüß]+( [a-z0-9äöüß]+)*)*$'
