from europepmc import fetch_europepmc_papers

papers = fetch_europepmc_papers(50)
print(len(papers))
