# CSV Source

This is a guide meant for tornament organizers or people making/using CSVs for team sources.

If you're using skip to the [Installation guide](#installation-guide). If you're making skip to the [Setup guide](#setup-guide)

## Setup guide
Source names are determined by a CSV file's name which can support spaces, however, should generally only stick to regular ASCII characters. Here is an example of the **most minimal** CSV file to supply a source for team rosters:

```csv
Team,Player,
Gryphons,Talon,
Gryphons,Plume,
Gryphons,Aerie,
Gryphons,Crest,
Gryphons,Quill,
Gryphons,Roost,
Ravens,Corvid,
Ravens,Murder,
Ravens,Caw,
Ravens,Nevermore,
Ravens,Onyx,
```


Team names and the first line are **capitalization and space sensitive**:

- `teAm,plaYer` ❌
- `Team,Player` ✅

Otherwise, your CSV file will fail to be parsed properly. As well, `grYpHons` **not equal to** `Gryphons`.

### Metadata / Extra data

You can attach additional **optional** data! Many overlay features can take advantage of mapping player to their extra info which the file can do here. Consider a **valid** csv file: 
```csv
Team,Player,Tracker
Gryphons,Talon,https://tracker.gg/valorant/profile/riot/Talon%23GRY/overview
Gryphons,Plume,https://tracker.gg/valorant/profile/riot/Plume%23GRY/overview
Gryphons,Aerie,
Gryphons,Crest,
```
A Valorant statline page will be able to trivially pull the stat line information from `Talon` and `Plume`. However, for players like `Aerie` and `Crest` it will not be able to. 

Additional information is generally **preferred** if not **required** by your tournament organizers, however, is not required to be always filled by per player. Please refer to the tournament organizers to get further clarification.


## Installation guide

Installation is trivial, simply drag your csv file which you've downloaded into `app/teams` folder. From there, the new csv source should be detected.


