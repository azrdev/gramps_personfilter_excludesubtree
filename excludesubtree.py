#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Jonathan Biegert
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import itertools
import logging

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters.rules.person import MatchesFilter
from gramps.gen.filters.rules import Rule
from gramps.gui.editors.filtereditor import MyBoolean

_ = glocale.translation.gettext

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.lib import Person
from gramps.gen.db import Database

LOG = logging.getLogger(__name__)


def get_relatives(db, person):
    """
    Given a person handle, iterate all existing person handles of its
    relatives.

    adapted from IsRelatedWith.add_relative()
    """
    if person:
        for h in itertools.chain(
                # person as child
                person.get_parent_family_handle_list(),
                # person as parent
                person.get_family_handle_list(),
                ):
            family = db.get_family_from_handle(h)
            if family:
                # parents / spouse
                for parent in (family.get_father_handle(),
                               family.get_mother_handle()):
                    if parent:
                        yield parent
                # siblings / children
                for child_ref in family.get_child_ref_list():
                    yield child_ref.ref


class GUICheckBox(MyBoolean):
    """
    Input widget for a boolean filter rule parameter.

    Needed because gramps.gui.editors.filtereditor defines MyBoolean widget
    with a single `label: str` parameter, but creates custom widgets with a
    single argument `db` in EditRule.__init__
    """
    def __init__(self, db, *args, **kwargs):
        super().__init__('', *args, **kwargs)  # first argument must be string (hidden label)


# -------------------------------------------------------------------------
#
# ExcludeSubtree
#
# -------------------------------------------------------------------------
class ExcludeSubtree(Rule):
    """
    Person filter rule including all persons reachable (parents/children in the same families) from the active/selected person, except those in the given filter.

    This allows to cut partial trees, e.g. exclude everything learned about my spouse but have all non-relatives in my half of the tree.
    """

    # filter rule operation
    selected_handles: Set[PrimaryObjectHandle] = None
    filt = None  # "stop" person filter

    # external interface
    labels = [
        # rule parameters, see
        # gramps.gui.editors.filtereditor.EditRule.__init__
        # must be (label, widget class) or special string as label
        _('ID:'),  # starting person
        (_('Include filter matches'), GUICheckBox),
        _('Person filter name:'),  # TODO: also allow family filter
    ]
    name = _("People reachable from <Person>, stopping at <Filter> matches")
    category = _("Relationship filters")
    description = _("Matches people who are reachable starting from <Person> "
                    "(walking all parents and children of attached families, "
                    "recursively) stopping at persons in <Filter>.")

    def prepare(self, db: Database, user):
        self.reset()
        self.db = db

        if user:
            user.begin_progress(self.category,
                                _('Retrieving all sub-filter matches'),
                                db.get_number_of_people())
        try:
            # initialize search from filter parameters (passed as self.list)
            start_person = db.get_person_from_gramps_id(self.list[0])
            if start_person is None:
                return
            include_matched = bool(int(self.list[1]))
            self.filt = MatchesFilter(self.list[2:])
            self.filt.requestprepare(db, user)

            # walk the db using a queue
            search_list: List[PrimaryObjectHandle] = [start_person.handle]
            while search_list:
                current_h = search_list.pop()
                if current_h in self.selected_handles:
                    continue  # already got them
                if user:
                    user.step_progress()
                current = db.get_person_from_handle(current_h)
                LOG.debug("tree walk arrived at id %s", current.gramps_id)
                if self.filt.apply_to_one(db, current):
                    LOG.debug("Stopping at filter match %s", current.gramps_id)
                    if include_matched:
                        self.selected_handles.add(current_h)
                    continue  # stop at filter matches
                self.selected_handles.add(current_h)
                # add their relatives to the search
                search_list.extend((h
                                    for h in get_relatives(db, current)
                                    if h))
            LOG.debug("Found %d relatives", len(self.selected_handles))

        finally:
            if user:
                user.end_progress()

    def reset(self):
        self.selected_handles = set()
        if self.filt:
            self.filt.requestreset()

    def apply_to_one(self, db: Database, person: Person) -> bool:
        return person.handle in self.selected_handles
