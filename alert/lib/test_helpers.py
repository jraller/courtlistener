import os
import time
from django.test import TestCase
from alert.audio.models import Audio
from alert.lib import sunburnt
from alert.lib.solr_core_admin import create_solr_core, swap_solr_core, \
    delete_solr_core
from alert.scrapers.management.commands.cl_scrape_oral_arguments import \
    Command
from alert.scrapers.test_assets import test_opinion_scraper, \
    test_oral_arg_scraper
from alert.search.models import Court, Citation, Docket, Document
from django.conf import settings


class SolrTestCase(TestCase):
    """A generic class that contains the setUp and tearDown functions for
    inheriting children.

    Good for tests with both audio and documents.
    """
    fixtures = ['test_court.json']

    def setUp(self):
        # Set up some handy variables
        self.court = Court.objects.get(pk='test')

        # Set up testing cores in Solr and swap them in
        self.core_name_opinion = '%s.opinion-test-%s' % \
                                 (self.__module__, time.time())
        self.core_name_audio = '%s.audio-test-%s' % \
                               (self.__module__, time.time())
        create_solr_core(self.core_name_opinion)
        create_solr_core(
            self.core_name_audio,
            schema=os.path.join(settings.INSTALL_ROOT, 'Solr', 'conf',
                                'audio_schema.xml'),
            instance_dir='/usr/local/solr/example/solr/audio',
        )
        swap_solr_core('collection1', self.core_name_opinion)
        swap_solr_core('audio', self.core_name_audio)
        self.si_opinion = sunburnt.SolrInterface(
            settings.SOLR_OPINION_URL, mode='rw')
        self.si_audio = sunburnt.SolrInterface(
            settings.SOLR_AUDIO_URL, mode='rw')

        # Add three documents and three audio files to the index, but don't
        # extract their contents
        self.site_opinion = test_opinion_scraper.Site().parse()
        self.site_audio = test_oral_arg_scraper.Site().parse()
        cite_counts = (4, 6, 8)
        self.docs = {}
        for i in range(0, 3):
            cite = Citation(
                case_name=self.site_opinion.case_names[i],
                docket_number=self.site_opinion.docket_numbers[i],
                neutral_cite=self.site_opinion.neutral_citations[i],
                federal_cite_one=self.site_opinion.west_citations[i],
            )
            cite.save(index=False)
            docket = Docket(
                case_name=self.site_opinion.case_names[i],
                court=self.court,
            )
            docket.save()
            self.docs[i] = Document(
                date_filed=self.site_opinion.case_dates[i],
                citation=cite,
                docket=docket,
                precedential_status=self.site_opinion.precedential_statuses[i],
                citation_count=cite_counts[i],
                nature_of_suit=self.site_opinion.nature_of_suit[i],
                judges=self.site_opinion.judges[i],
            )
            self.docs[i].save()

        # Create citations between the documents
        # 0 ---cites--> 1, 2
        # 1 ---cites--> 2
        # 2 ---cites--> 0
        self.docs[0].cases_cited.add(self.docs[1].citation)
        self.docs[0].cases_cited.add(self.docs[2].citation)
        self.docs[1].cases_cited.add(self.docs[2].citation)
        self.docs[2].cases_cited.add(self.docs[0].citation)

        for doc in self.docs.itervalues():
            doc.save()

        # Scrape the audio "site" and add its contents
        site = test_oral_arg_scraper.Site().parse()
        Command().scrape_court(site, full_crawl=True)

        self.expected_num_results_opinion = 3
        self.expected_num_results_audio = 2

    def tearDown(self):
        Document.objects.all().delete()
        Audio.objects.all().delete()
        swap_solr_core(self.core_name_opinion, 'collection1')
        swap_solr_core(self.core_name_audio, 'audio')
        delete_solr_core(self.core_name_opinion)
        delete_solr_core(self.core_name_audio)
