import re
from django.db.models.signals import pre_save
from django.dispatch import receiver
from alert import settings
from alert.lib.model_helpers import make_upload_path
from alert.lib.string_utils import trunc
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.text import slugify
from django.utils.encoding import smart_unicode


# changes here need to be mirrored in the coverage page view and Solr configs
# Note that spaces cannot be used in the keys, or else the SearchForm won't work
JURISDICTIONS = (
    ('F', 'Federal Appellate'),
    ('FD', 'Federal District'),
    ('FB', 'Federal Bankruptcy'),
    ('FBP', 'Federal Bankruptcy Panel'),
    ('FS', 'Federal Special'),
    ('S', 'State Supreme'),
    ('SA', 'State Appellate'),
    ('SS', 'State Special'),
    ('C', 'Committee'),
    ('T', 'Testing'),
)

DOCUMENT_STATUSES = (
    ('Published', 'Precedential'),
    ('Unpublished', 'Non-Precedential'),
    ('Errata', 'Errata'),
    ('Memorandum Decision', 'Memorandum Decision'),
    ('Per Curiam Opinion', 'Per Curiam Opinion'),
    ('Separate', 'Separate Opinion'),
    ('Signed Opinion', 'Signed Opinion'),
    ('In-chambers', 'In-chambers'),
    ('Relating-to', 'Relating-to orders'),
    ('Unknown', 'Unknown Status'),
)

SOURCES = (
    ('C', 'court website'),
    ('R', 'resource.org'),
    ('CR', 'court website merged with resource.org'),
    ('L', 'lawbox'),
    ('LC', 'lawbox merged with court'),
    ('LR', 'lawbox merged with resource.org'),
    ('LCR', 'lawbox merged with court and resource.org'),
    ('M', 'manual input'),
    ('A', 'internet archive'),
)


class Docket(models.Model):
    """A class to sit above Documents and Audio files and link them together"""
    date_modified = models.DateTimeField(
        help_text="The last moment when the item was modified. A value in year 1750 indicates the value is unknown",
        auto_now=True,
        editable=False,
        db_index=True,
        null=True,
    )
    court = models.ForeignKey(
        'Court',
        help_text="The court where the docket was filed",
        db_index=True,
        null=True
    )
    case_name = models.TextField(
        help_text="The full name of the case",
        blank=True
    )
    slug = models.SlugField(
        help_text="URL that the document should map to (the slug)",
        max_length=50,
        null=True
    )
    date_blocked = models.DateField(
        help_text="The date that this opinion was blocked from indexing by search engines",
        blank=True,
        null=True,
        db_index=True,
    )
    blocked = models.BooleanField(
        help_text="Whether a document should be blocked from indexing by search engines",
        db_index=True,
        default=False
    )

    def __unicode__(self):
        if self.case_name:
            return smart_unicode('%s: %s' % (self.pk, self.case_name))
        else:
            return str(self.pk)

    def save(self, *args, **kwargs):
        self.slug = trunc(slugify(self.case_name), 50)
        super(Docket, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('view_docket', args=[self.pk, self.slug])


class Court(models.Model):
    """A class to represent some information about each court, can be extended
    as needed."""
    id = models.CharField(
        help_text='a unique ID for each court as used in URLs',
        max_length=15,
        primary_key=True
    )
    date_modified = models.DateTimeField(
        help_text="The last moment when the item was modified",
        auto_now=True,
        editable=False,
        db_index=True,
        null=True
    )
    in_use = models.BooleanField(
        help_text='Whether this jurisdiction is in use in CourtListener -- increasingly True',
        default=False
    )
    has_opinion_scraper = models.BooleanField(
        help_text='Whether the jurisdiction has a scraper that obtains opinions automatically.',
        default=False,
    )
    has_oral_argument_scraper = models.BooleanField(
        help_text='Whather the jurisdiction has a scraper that obtains oral arguments automatically.',
        default=False,
    )
    position = models.FloatField(
        help_text='A dewey-decimal-style numeral indicating a hierarchical ordering of jurisdictions',
        null=True,
        db_index=True,
        unique=True
    )
    citation_string = models.CharField(
        help_text='the citation abbreviation for the court as dictated by Blue Book',
        max_length=100,
        blank=True
    )
    short_name = models.CharField(
        help_text='a short name of the court',
        max_length=100,
        blank=False
    )
    full_name = models.CharField(
        help_text='the full name of the court',
        max_length='200',
        blank=False
    )
    url = models.URLField(
        help_text='the homepage for each court or the closest thing thereto',
        max_length=500,
    )
    start_date = models.DateField(
        help_text="the date the court was established, if known",
        blank=True,
        null=True
    )
    end_date = models.DateField(
        help_text="the date the court was abolished, if known",
        blank=True,
        null=True
    )
    jurisdiction = models.CharField(
        help_text='the jurisdiction of the court, one of: %s' % ', '.join(['%s (%s)' % (t[0], t[1])
                                                                           for t in JURISDICTIONS]),
        max_length=3,
        choices=JURISDICTIONS
    )
    notes = models.TextField(
        help_text="any notes about coverage or anything else (currently very raw)",
        blank=True
    )

    def __unicode__(self):
        return self.full_name

    class Meta:
        db_table = "Court"
        ordering = ["position"]


class Citation(models.Model):
    slug = models.SlugField(
        help_text="URL that the document should map to (the slug)",
        max_length=50,
        null=True
    )
    case_name = models.TextField(
        help_text="The full name of the case",
        blank=True
    )
    docket_number = models.CharField(
        help_text="The docket numbers of a case, can be consolidated and quite long",
        max_length=5000,  # sometimes these are consolidated, hence they need to be long (was 50, 100, 300, 1000).
        blank=True,
        null=True
    )
    federal_cite_one = models.CharField(
        help_text="Primary federal citation",
        max_length=50,
        blank=True,
        null=True
    )
    federal_cite_two = models.CharField(
        help_text="Secondary federal citation",
        max_length=50,
        blank=True,
        null=True
    )
    federal_cite_three = models.CharField(
        help_text="Tertiary federal citation",
        max_length=50,
        blank=True,
        null=True
    )
    state_cite_one = models.CharField(
        help_text="Primary state citation",
        max_length=50,
        blank=True,
        null=True
    )
    state_cite_two = models.CharField(
        help_text="Secondary state citation",
        max_length=50,
        blank=True,
        null=True
    )
    state_cite_three = models.CharField(
        help_text="Tertiary state citation",
        max_length=50,
        blank=True,
        null=True
    )
    state_cite_regional = models.CharField(
        help_text="Regional citation",
        max_length=50,
        blank=True,
        null=True
    )
    specialty_cite_one = models.CharField(
        help_text="Specialty citation",
        max_length=50,
        blank=True,
        null=True
    )
    scotus_early_cite = models.CharField(
        help_text="Early SCOTUS citation such as How., Black, Cranch., etc.",
        max_length=50,
        blank=True,
        null=True
    )
    lexis_cite = models.CharField(
        help_text="Lexis Nexus citation (e.g. 1 LEXIS 38237)",
        max_length=50,
        blank=True,
        null=True
    )
    westlaw_cite = models.CharField(
        help_text="WestLaw citation (e.g. 22 WL 238)",
        max_length=50,
        blank=True,
        null=True
    )
    neutral_cite = models.CharField(
        help_text='Neutral citation',
        max_length=50,
        blank=True,
        null=True
    )

    def save(self, index=True, *args, **kwargs):
        """
        Note that there is a pre_save receiver below.
        """
        created = self.pk is None
        self.slug = trunc(slugify(self.case_name), 50)
        super(Citation, self).save(*args, **kwargs)

        # We only do this on update, not creation
        if index and not created:
            # Import is here to avoid looped import problem
            from search.tasks import update_cite
            update_cite.delay(self.pk)

    def __unicode__(self):
        if self.case_name:
            return smart_unicode('%s: %s' % (self.pk, self.case_name))
        else:
            return str(self.pk)

    class Meta:
        db_table = "Citation"


@receiver(pre_save, sender=Citation)
def update_dockets_if_citation_case_name_changed(sender, instance, **kwargs):
    """Updates the docket.case_name field for all associated Dockets when the
    Citation.case_name field changes.

     - From http://stackoverflow.com/a/7934958/64911.

    There are a few alternative ways to implement this that don't hit the database
    an extra time (as this one does). However, those solutions are longer and more
    controversial, so I chose this one based on the fact that we rarely change
    objects once they are saved and the performance penalty is probably acceptable.
    """
    try:
        cite = Citation.objects.get(pk=instance.pk)
    except Citation.DoesNotExist:
        # Object is new
        pass
    else:
        if not cite.case_name == instance.case_name:
            # Update the associated dockets
            for d in cite.parent_documents.all():
                d.docket.case_name = instance.case_name
                d.docket.slug = trunc(slugify(instance.case_name), 50)
                d.docket.save()


class Document(models.Model):
    """A class representing a single court opinion.

    This must go last, since it references the above classes
    """
    time_retrieved = models.DateTimeField(
        help_text="The original creation date for the item",
        auto_now_add=True,
        editable=False,
        db_index=True
    )
    date_modified = models.DateTimeField(
        help_text="The last moment when the item was modified. A value in year 1750 indicates the value is unknown",
        auto_now=True,
        editable=False,
        db_index=True,
        null=True,
    )
    date_filed = models.DateField(
        help_text="The date filed by the court",
        blank=True,
        null=True,
        db_index=True
    )
    source = models.CharField(
        help_text="the source of the document, one of: %s" % ', '.join(['%s (%s)' % (t[0], t[1]) for t in SOURCES]),
        max_length=3,
        choices=SOURCES,
        blank=True
    )
    sha1 = models.CharField(
        help_text="unique ID for the document, as generated via SHA1 of the binary file or text data",
        max_length=40,
        db_index=True
    )
    citation = models.ForeignKey(
        Citation,
        help_text="The citation object for the document",
        related_name="parent_documents",
        blank=True,
        null=True
    )
    docket = models.ForeignKey(
        Docket,
        help_text="The docket that the document is a part of",
        related_name="documents",
        blank=True,
        null=True
    )
    download_url = models.URLField(
        help_text="The URL on the court website where the document was originally scraped",
        max_length=500,
        db_index=True,
        null=True,
        blank=True,
    )
    local_path = models.FileField(
        help_text="The location, relative to MEDIA_ROOT on the CourtListener server, where files are stored",
        upload_to=make_upload_path,
        blank=True,
        db_index=True
    )
    judges = models.TextField(
        help_text="The judges that brought the opinion as a simple text string",
        blank=True,
        null=True,
    )
    nature_of_suit = models.TextField(
        help_text="The nature of the suit. For the moment can be codes or laws or whatever",
        blank=True
    )
    plain_text = models.TextField(
        help_text="Plain text of the document after extraction using pdftotext, wpd2txt, etc.",
        blank=True
    )
    html = models.TextField(
        help_text="HTML of the document, if available in the original",
        blank=True,
        null=True,
    )
    html_lawbox = models.TextField(
        help_text='HTML of lawbox documents',
        blank=True,
        null=True,
    )
    html_with_citations = models.TextField(
        help_text="HTML of the document with citation links and other post-processed markup added",
        blank=True
    )
    cases_cited = models.ManyToManyField(
        Citation,
        help_text="Opinions cited by this opinion",
        related_name="citing_opinions",
        null=True,
        blank=True
    )
    citation_count = models.IntegerField(
        help_text='The number of times this document is cited by other opinion',
        default=0,
        db_index=True,
    )
    precedential_status = models.CharField(
        help_text='The precedential status of document, one of: %s' % ', '.join([t[0] for t in DOCUMENT_STATUSES]),
        max_length=50,
        blank=True,
        choices=DOCUMENT_STATUSES,
        db_index=True,
    )
    date_blocked = models.DateField(
        help_text="The date that this opinion was blocked from indexing by search engines",
        blank=True,
        null=True,
        db_index=True,
    )
    blocked = models.BooleanField(
        help_text="Whether a document should be blocked from indexing by search engines",
        db_index=True,
        default=False
    )
    extracted_by_ocr = models.BooleanField(
        help_text='Whether OCR was used to get this document content',
        default=False,
        db_index=True,
    )
    is_stub_document = models.BooleanField(
        'Whether this document is a stub or not',
        default=False
    )

    @property
    def caption(self):
        """Make a proper caption"""
        caption = self.docket.case_name
        if self.citation.neutral_cite:
            caption += ", %s" % self.citation.neutral_cite
            return caption  # neutral cites lack the parentheses, so we're done here.
        elif self.citation.federal_cite_one:
            caption += ", %s" % self.citation.federal_cite_one
        elif self.citation.specialty_cite_one:
            caption += ", %s" % self.citation.specialty_cite_one
        elif self.citation.state_cite_regional:
            caption += ", %s" % self.citation.state_cite_regional
        elif self.citation.state_cite_one:
            caption += ", %s" % self.citation.state_cite_one
        elif self.citation.westlaw_cite and self.citation.lexis_cite:
            # If both WL and LEXIS
            caption += ", %s, %s" % (self.citation.westlaw_cite, self.citation.lexis_cite)
        elif self.citation.westlaw_cite:
            # If only WL
            caption += ", %s" % self.citation.westlaw_cite
        elif self.citation.lexis_cite:
            # If only LEXIS
            caption += ", %s" % self.citation.lexis_cite
        elif self.citation.docket_number:
            caption += ", %s" % self.citation.docket_number
        caption += ' ('
        if self.docket.court.citation_string != 'SCOTUS':
            caption += re.sub(' ', '&nbsp;', self.docket.court.citation_string)
            caption += '&nbsp;'
        caption += '%s)' % self.date_filed.isoformat().split('-')[0]  # b/c strftime f's up before 1900.
        return caption

    def __unicode__(self):
        if self.citation:
            return '%s: %s' % (self.pk, self.citation.case_name)
        else:
            return str(self.pk)

    def get_absolute_url(self):
        return reverse('view_case', args=[self.pk, self.citation.slug])

    def save(self, index=True, commit=True, *args, **kwargs):
        """
        If the value of blocked changed to True, invalidate the caches
        where that value was stored. Google can later pick it up properly.
        """
        super(Document, self).save(*args, **kwargs)

        if index:
            from search.tasks import add_or_update_doc
            add_or_update_doc.delay(self.pk, commit)

    def delete(self, *args, **kwargs):
        """
        If the item is deleted, we need to update the caches that previously
        contained it. Note that this doesn't get called when an entire queryset
        is deleted, but that should be OK.
        """
        id_cache = self.pk
        super(Document, self).delete(*args, **kwargs)
        from search.tasks import delete_item
        delete_item.delay(id_cache, settings.SOLR_OPINION_URL)

    class Meta:
        db_table = "Document"


def save_doc_and_cite(doc, index):
    """Save a document and citation simultaneously.

    Just a helper function to save everything neatly.
    """
    cite = doc.citation
    cite.save(index=index)
    doc.citation = cite
    doc.save(index=index)
