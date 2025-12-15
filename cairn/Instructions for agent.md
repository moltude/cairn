These are additional features which I want to implement.


1. All of the sub-command of the CLI are not necessary
1a. Convert could be a sub command of migrate or removed entirely; investigate what is actually used for and does. if it is not used then remove it.
1b. icon I don't think the cli is the right tool to manage the icon mappings, that is better done in the config files directly.
1c. config - A config subcommand would be useful but this does not do what I would want to at all. We need to adjust what is and is not configurable.
1d. Users should be able to default path for maps for example /Users/scott/maps/


2. When editing the elements of a map in the CLI a user should be able to perform bulk updates. Currently users are allowed to select one item at a time. To select multiple items users can enter the following:
1,2,3
1, 2,3
1-4 This will update entries 1,2,3,4
all - which will update all data points

The same fields should be editable.

Name, Description, Icon, Color

The use case for this is to be able to select multiple waypoints that are known to be water and edit them to standard values of:

Name: Water
Icon: Water
Color: Blue
Making bulk updates in OnX is either not possible or very difficult.

This change will require adding additional data validation to the input ie a user entered 1,3,5 when only 1-4 exist or 1-9 when only 6 entries exist.


3. The 'Migration Summary:' block should show the same kind of summary at the top of the process

Days - Sorted Tracks (7)
────────────────────────────────────────────────────────────
    1. ■ 8/24 - Monday
    2. ■ 8/25 - Tuesday
    3. ■ 8/26 - Wednesday
    4. ■ 8/27 - Thursday
    5. ■ 8/28 - Friday
    6. ■ 8/29 - Saturday
    7. ■ 8/30 - Sunday
────────────────────────────────────────────────────────────
Order confirmed (--yes flag)

Entire Route - Sorted Tracks (1)
────────────────────────────────────────────────────────────
    1. ■ Entire route
────────────────────────────────────────────────────────────
Order confirmed (--yes flag)

Uncategorized - Sorted Waypoints (3)
────────────────────────────────────────────────────────────
    1. Exit [Location]
    2. Peak + Photos [View]
    3. Start [Location]
────────────────────────────────────────────────────────────

There should be a final prompt of 'Ready to generate new map' Y/n
> If no is selected then there should be a prompt to continue making revisions or abort so perhaps

Y/n/abort or Yes/abort/resume -- I'm not sure which version or language makes the most sense for this kind of operatoin.

This information
--------
Input File:
  San_Juans.json (13.4 MB)

Content:
  Folders: 3
  Waypoints: 3
  Tracks: 8
  Shapes: 0

Output Directory:
  demo/caltopo-to-onx/san juans/onx_ready

Output Files (will be created):
  • GPX files for waypoints and tracks
  • KML files for shapes/polygons
  • Summary files (if icon prefixes used)

Processing Options:
  Natural sorting: Yes
--------
Is not necessary only a summary like of
    Data written to <output directory>
Should be printed at the end.

4. Do not create a SUMMARY file anymore, that was only used for debugging

5. Investigate if there is a level of generalization that we can apply now. It seems like we are more generic than simply caltopo to onx and onx to caltopo. It is simply 'migrate to onx' or 'migrate to caltopo'. If there are absractions which can be made in this regard I would like to know what they are. It would simplify the CLI invocation to 'cairn migrate onx' or 'cairn migrate caltopo'.  That would also allow for GPX, KML and GeoJSON files as source files. Does this impact the current structure of our mappings and exports into OnX and CalTopo? Refactor functions, classes, objects to these more generic names.

6. Based on our testing so far does it seem feasiable to export data from OnX, modify it and then reimport it have it it update teh same datapoints without creating new ones? This might be an interesting feature but I am skeptical if it is possible

7. "Found 2 unmapped CalTopo symbol(s):" This warning at the end of the import process should be a warning at the top of the process so those icons can be mapped if wanted.

8. Any invalidate data entered during the CLI process should not abort the process. This is true of the inital directory prompt. If there are not JSON, KML or GPX files in the directory then it should reprompt. If the directory does not exist it should reprompt.

9. Check for any dead or deprecated code after these changes
.
10. Check coverages
    Update any existing tests after these changes
    Create any new required unit, integration or data validation checks

11. Update documentation
